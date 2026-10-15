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


@dataclass
class TaskServiceRecord:
    """
    Tracked execution and utility metrics per LO task.
    """

    task_id: int
    task_name: str
    utility: float
    utility_density: float
    requested_execution: float
    allocated_execution: float
    achieved_execution: float
    achieved_service_fraction: float
    achieved_utility: float


class DegradationController:
    """
    Utility-Aware Degradation Controller engine.
    """

    def __init__(
        self,
        tasks: List[Task],
        warning_enter: float = 0.60,
        hi_enter: float = 0.80,
        ablation_config: Optional[Any] = None,
    ) -> None:
        self.tasks: List[Task] = tasks
        self.warning_enter: float = warning_enter
        self.hi_enter: float = hi_enter
        self.ablation_config: Optional[Any] = ablation_config
        # Map task_id -> current assigned service_level
        self.current_service_levels: Dict[int, float] = {t.task_id: 1.00 for t in tasks}
        self.service_change_log: List[ServiceChangeEvent] = []
        self.task_service_records: Dict[int, TaskServiceRecord] = {}

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

    def determine_available_capacity(
        self,
        mode: Any,
        risk: float = 0.0,
        explicit_capacity: Optional[float] = None,
    ) -> float:
        """
        Determine remaining CPU utilization capacity available for LO tasks.

        Guarantees HI workload protection:
            U_HI is subtracted from total capacity 1.0.
            Available capacity for LO is max(0.0, 1.0 - U_HI).
        """
        if explicit_capacity is not None:
            return max(0.0, explicit_capacity)

        mode_str = getattr(mode, "value", str(mode)).upper()

        hi_tasks = [t for t in self.tasks if t.criticality == Criticality.HI]
        u_hi_lo = sum(t.C_LO / t.period for t in hi_tasks)
        u_hi_hi = sum(t.C_HI / t.period for t in hi_tasks)

        if mode_str in ("HI", "HIGH"):
            # In HI mode: protect worst-case HI execution (C_HI)
            u_hi = u_hi_hi
        elif mode_str in ("WARNING",):
            # In WARNING mode: interpolate HI demand based on risk
            severity = max(0.0, min(1.0, (risk - self.warning_enter) / max(1e-6, self.hi_enter - self.warning_enter)))
            u_hi = u_hi_lo + severity * (u_hi_hi - u_hi_lo)
        else:
            # LO or RECOVERY mode: normal nominal HI load
            u_hi = u_hi_lo

        return max(0.0, 1.0 - u_hi)

    def allocate_service_levels(
        self, available_capacity: float
    ) -> Dict[int, float]:
        """
        Allocate discrete service levels to LO tasks to maximize total utility:
            maximize sum(utility_i * s_i)
            subject to sum(s_i * (C_LO_i / T_i)) <= available_capacity
            s_i in (1.00, 0.75, 0.50, 0.25, 0.00)

        Algorithm:
            1. Rank LO tasks by utility density descending.
            2. Greedily select the largest allowed service level s_i for each task
               such that s_i * (C_LO_i / T_i) <= remaining_capacity.
            3. Deduct consumed capacity and repeat for remaining tasks.
        """
        lo_ranked = rank_lo_tasks_by_utility_density(self.tasks)
        rem_cap = max(0.0, available_capacity)
        allocations: Dict[int, float] = {}

        for task in lo_ranked:
            u_full = task.C_LO / task.period
            selected_s = 0.0
            for s in ALLOWED_SERVICE_LEVELS:
                if s * u_full <= rem_cap + 1e-6:
                    selected_s = s
                    break

            allocations[task.task_id] = selected_s
            rem_cap = max(0.0, rem_cap - selected_s * u_full)

        return allocations

    def update(
        self,
        current_time: float,
        mode: Any,
        risk: float,
        overridden_service_levels: Optional[Dict[int, float]] = None,
        available_capacity: Optional[float] = None,
    ) -> Dict[int, float]:
        """
        Dynamically adjust LO task service levels based on available CPU capacity and utility density.

        In LO mode: full service (1.00) if capacity permits.
        In WARNING/HI mode: allocate capacity to highest utility density tasks first.
        """
        if overridden_service_levels:
            for task in self.tasks:
                if task.task_id in overridden_service_levels:
                    s = overridden_service_levels[task.task_id]
                    self.set_task_service_level(
                        current_time, task, s, f"Service level override during {getattr(mode, 'value', str(mode))}"
                    )
            return self.current_service_levels

        avail_cap = self.determine_available_capacity(mode, risk, explicit_capacity=available_capacity)
        mode_str = getattr(mode, "value", str(mode)).upper()

        enable_degradation = getattr(self.ablation_config, "enable_degradation", True) if getattr(self, "ablation_config", None) else True
        enable_utility = getattr(self.ablation_config, "enable_utility_degradation", True) if getattr(self, "ablation_config", None) else True

        if mode_str in ("LO", "LOW"):
            lo_tasks = [t for t in self.tasks if t.criticality == Criticality.LO]
            for t in lo_tasks:
                self.set_task_service_level(current_time, t, 1.00, "LO mode: full service")
            return self.current_service_levels

        # Overload / Constrained / HI / WARNING mode
        if not enable_degradation:
            # Complete shedding of all LO tasks
            for task in self.tasks:
                if task.criticality == Criticality.LO:
                    self.set_task_service_level(
                        current_time,
                        task,
                        0.00,
                        f"{mode_str} mode: degradation disabled (complete shedding)",
                    )
            return self.current_service_levels

        if not enable_utility:
            # Generic uniform degradation without utility awareness
            generic_s = getattr(self.ablation_config, "generic_degraded_service_level", 0.50) if getattr(self, "ablation_config", None) else 0.50
            for task in self.tasks:
                if task.criticality == Criticality.LO:
                    self.set_task_service_level(
                        current_time,
                        task,
                        generic_s,
                        f"{mode_str} mode: generic uniform degradation (s={generic_s:.2f})",
                    )
            return self.current_service_levels

        # Utility-aware degradation: rank by utility density and optimize
        avail_cap = self.determine_available_capacity(mode, risk, explicit_capacity=available_capacity)
        allocations = self.allocate_service_levels(avail_cap)
        for task in self.tasks:
            if task.criticality == Criticality.LO:
                new_service = allocations.get(task.task_id, 0.00)
                self.set_task_service_level(
                    current_time,
                    task,
                    new_service,
                    f"{mode_str} mode (avail_cap={avail_cap:.3f}, risk={risk:.2f}): utility-density allocation",
                )

        return self.current_service_levels

    def calculate_utility_metrics(
        self, completed_jobs: List[Any], released_jobs: List[Any]
    ) -> Dict[str, Any]:
        """
        Calculate total achieved LO utility, max possible LO utility, utility ratio,
        and per-task service records tracking:
          - requested execution
          - allocated execution
          - achieved service fraction
          - utility
          - achieved utility
        """
        lo_tasks = [t for t in self.tasks if t.criticality == Criticality.LO]
        max_possible_utility = sum(t.utility for t in lo_tasks)

        lo_utility = 0.0
        task_records: Dict[int, TaskServiceRecord] = {}

        for task in lo_tasks:
            task_released = [j for j in released_jobs if j.task.task_id == task.task_id]
            task_completed = [j for j in completed_jobs if j.task.task_id == task.task_id]

            density = calculate_utility_density(task)
            req_sum = sum(getattr(j, "nominal_execution", j.task.C_LO) for j in task_released)
            alloc_sum = sum(j.required_execution for j in task_released)
            exec_sum = sum(j.executed_time for j in task_completed)

            if not task_released:
                service_fraction = 1.0
            else:
                service_fraction = min(1.0, (exec_sum / req_sum)) if req_sum > 0 else 0.0

            achieved = task.utility * service_fraction
            lo_utility += achieved

            record = TaskServiceRecord(
                task_id=task.task_id,
                task_name=task.name,
                utility=task.utility,
                utility_density=density,
                requested_execution=req_sum,
                allocated_execution=alloc_sum,
                achieved_execution=exec_sum,
                achieved_service_fraction=service_fraction,
                achieved_utility=achieved,
            )
            task_records[task.task_id] = record

        self.task_service_records = task_records
        ratio = (lo_utility / max_possible_utility) if max_possible_utility > 0 else 1.0

        return {
            "LO_utility": lo_utility,
            "maximum_possible_LO_utility": max_possible_utility,
            "LO_utility_ratio": ratio,
            "task_reports": task_records,
        }


# Alias for backwards and forwards compatibility
UtilityAwareDegradationController = DegradationController

