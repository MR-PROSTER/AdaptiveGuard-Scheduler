"""
Utility-Aware LO Degradation Controller.

Ranks LO tasks dynamically by utility density:
    utility_density = utility / execution_cost (C_LO)

Allowed Service Levels:
    1.00, 0.75, 0.50, 0.25, 0.00

In LO mode:
    All LO tasks = 1.00 service level

In WARNING mode:
    Protect HI tasks. Reduce service of lower utility-density LO tasks FIRST.
    Do NOT reduce every LO task equally. Maximize total completed LO utility.

In HI mode:
    HI tasks protected (service level = 1.00). LO tasks shed or degraded.

HI tasks are NEVER degraded.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from simulator.task import Task, Criticality
from controllers.mode_controller import SystemMode

ALLOWED_SERVICE_LEVELS = (1.00, 0.75, 0.50, 0.25, 0.00)


def calculate_utility_density(task: Task) -> float:
    """
    Calculate application utility density for a task.

    Formula:
        utility_density = utility / C_LO
    """
    if task.C_LO <= 0:
        raise ValueError(f"Task C_LO must be positive, got {task.C_LO}")
    return task.utility / task.C_LO


def rank_lo_tasks_by_utility_density(tasks: List[Task]) -> List[Task]:
    """
    Rank LO-criticality tasks in descending order of utility density.
    Tie-breaking: smaller task_id first.
    """
    lo_tasks = [t for t in tasks if t.criticality == Criticality.LO]
    return sorted(
        lo_tasks,
        key=lambda t: (calculate_utility_density(t), -t.task_id),
        reverse=True,
    )


@dataclass
class ServiceChangeEvent:
    """
    Record of a task service level change event.
    """

    time: float
    task_id: int
    task_name: str
    old_service: float
    new_service: float
    utility_density: float
    reason: str


class DegradationController:
    """
    Utility-Aware Degradation Controller engine.
    """

    def __init__(self, tasks: List[Task]) -> None:
        self.tasks: List[Task] = tasks
        # Map task_id -> current assigned service_level
        self.current_service_levels: Dict[int, float] = {t.task_id: 1.00 for t in tasks}
        self.service_change_log: List[ServiceChangeEvent] = []

    def get_service_level(self, task_id: int) -> float:
        """Return current service level for a task."""
        return self.current_service_levels.get(task_id, 1.00)

    def set_task_service_level(
        self, current_time: float, task: Task, new_service: float, reason: str
    ) -> None:
        """Set service level for a task and log if changed."""
        if task.criticality == Criticality.HI:
            # HI tasks are NEVER degraded
            new_service = 1.00

        # Snap to nearest allowed service level
        new_service = min(ALLOWED_SERVICE_LEVELS, key=lambda s: abs(s - new_service))

        old_service = self.get_service_level(task.task_id)
        if abs(old_service - new_service) > 1e-6:
            self.current_service_levels[task.task_id] = new_service
            density = calculate_utility_density(task) if task.criticality == Criticality.LO else 0.0
            event = ServiceChangeEvent(
                time=current_time,
                task_id=task.task_id,
                task_name=task.name,
                old_service=old_service,
                new_service=new_service,
                utility_density=density,
                reason=reason,
            )
            self.service_change_log.append(event)

    def update(
        self,
        current_time: float,
        mode: SystemMode,
        risk: float,
        overridden_service_levels: Optional[Dict[int, float]] = None,
    ) -> Dict[int, float]:
        """
        Dynamically adjust LO task service levels based on system mode and risk score.

        In LO mode: all LO tasks = 1.00
        In WARNING mode: reduce lower utility-density LO tasks FIRST.
        In HI mode: shed lower utility-density tasks to 0.00.
        """
        if overridden_service_levels:
            for task in self.tasks:
                if task.task_id in overridden_service_levels:
                    s = overridden_service_levels[task.task_id]
                    self.set_task_service_level(
                        current_time, task, s, f"Service level override during {mode.value}"
                    )
            return self.current_service_levels

        lo_ranked = rank_lo_tasks_by_utility_density(self.tasks)

        if mode == SystemMode.LO:
            for t in lo_ranked:
                self.set_task_service_level(current_time, t, 1.00, "LO mode: full service")

        elif mode == SystemMode.WARNING:
            warning_enter = 0.50
            hi_enter = 0.80
            raw_severity = (risk - warning_enter) / (hi_enter - warning_enter) if hi_enter > warning_enter else 0.5
            severity = max(0.05, min(1.0, raw_severity))
            num_lo = len(lo_ranked)

            for idx, t in enumerate(lo_ranked):
                # idx = 0 is highest utility density (Telemetry)
                # idx = num_lo - 1 is lowest utility density (Logging_C)
                # Lower density tasks (larger idx) get degraded first/more
                degrade_factor = (idx + 1) / num_lo
                target_service = 1.00 - severity * degrade_factor
                self.set_task_service_level(
                    current_time,
                    t,
                    target_service,
                    f"WARNING mode (risk={risk:.2f}): lower density task degraded first",
                )

        elif mode == SystemMode.HI:
            for idx, t in enumerate(lo_ranked):
                self.set_task_service_level(
                    current_time, t, 0.00, "HI mode: LO task shed to protect HI tasks"
                )

        return self.current_service_levels

    def calculate_utility_metrics(
        self, completed_jobs: List[Any], released_jobs: List[Any]
    ) -> Dict[str, float]:
        """
        Calculate total achieved LO utility, max possible LO utility, and utility ratio.

        For each LO task:
            achieved_utility = utility * achieved_service_fraction
            LO_utility = sum(achieved_utility)
            maximum_possible_LO_utility = sum(utility)
            LO_utility_ratio = LO_utility / maximum_possible_LO_utility
        """
        lo_tasks = [t for t in self.tasks if t.criticality == Criticality.LO]
        max_possible_utility = sum(t.utility for t in lo_tasks)

        lo_utility = 0.0
        for task in lo_tasks:
            task_released = [j for j in released_jobs if j.task.task_id == task.task_id]
            task_completed = [j for j in completed_jobs if j.task.task_id == task.task_id]

            if not task_released:
                service_fraction = 1.0
            else:
                exec_sum = sum(j.executed_time for j in task_completed)
                req_sum = sum(j.required_execution for j in task_released)
                service_fraction = (exec_sum / req_sum) if req_sum > 0 else 0.0

            achieved = task.utility * service_fraction
            lo_utility += achieved

        ratio = (lo_utility / max_possible_utility) if max_possible_utility > 0 else 1.0

        return {
            "LO_utility": lo_utility,
            "maximum_possible_LO_utility": max_possible_utility,
            "LO_utility_ratio": ratio,
        }
