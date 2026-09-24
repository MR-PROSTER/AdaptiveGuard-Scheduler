"""
EDF-VD + Degraded LO Service Scheduler.

Extends EDF-VD by providing degraded execution service to LO tasks in HI mode
rather than immediately dropping them completely.
(Note: This is a baseline model and not an exact implementation of Liu et al.)

Service Levels supported for LO tasks in HI mode:
  1.0, 0.75, 0.50, 0.25, 0.0

In HI mode:
- HI tasks remain protected with actual deadlines.
- LO tasks receive reduced service budget (degraded_service_level * C_LO).
"""

from typing import List, Optional, Tuple
from simulator.job import Job
from simulator.task import Task, Criticality
from schedulers.base_scheduler import BaseScheduler
from schedulers.edf_vd import calculate_x, virtual_deadline


class EDFVDDegradedScheduler(BaseScheduler):
    """
    EDF-VD + Degraded LO Service Baseline Scheduler.
    """

    SUPPORTED_SERVICE_LEVELS = (1.0, 0.75, 0.50, 0.25, 0.0)

    def __init__(
        self,
        tasks: Optional[List[Task]] = None,
        x: Optional[float] = None,
        degraded_service_level: float = 0.50,
        initial_mode: Criticality = Criticality.LO,
    ) -> None:
        super().__init__(name="EDF-VD + Degraded LO Service")
        self.current_mode: Criticality = initial_mode
        self.tasks: List[Task] = tasks or []

        if degraded_service_level not in self.SUPPORTED_SERVICE_LEVELS:
            raise ValueError(
                f"Unsupported degraded service level {degraded_service_level}. "
                f"Supported: {self.SUPPORTED_SERVICE_LEVELS}"
            )
        self.degraded_service_level: float = degraded_service_level

        if x is not None:
            self.x: float = x
        elif self.tasks:
            self.x = calculate_x(self.tasks)
        else:
            self.x = 1.0

    def set_mode(self, new_mode: Criticality) -> None:
        """Handle mode switch to HI mode with degraded LO service."""
        if self.current_mode != new_mode:
            self.current_mode = new_mode
            if new_mode == Criticality.HI:
                if self.degraded_service_level == 0.0:
                    # Drop LO tasks if 0.0 service
                    self.ready_queue = [
                        j for j in self.ready_queue if j.task.criticality == Criticality.HI
                    ]
                else:
                    # Apply degraded service scaling to active LO jobs
                    for job in self.ready_queue:
                        if job.task.criticality == Criticality.LO:
                            degraded_budget = job.task.C_LO * self.degraded_service_level
                            job.required_execution = degraded_budget
                            job.remaining_execution = max(
                                0.0, degraded_budget - job.executed_time
                            )

    def _get_priority_key(self, job: Job) -> Tuple[float, int, float, int]:
        """Priority key using virtual deadline in LO mode, actual deadline in HI mode."""
        eff_deadline = virtual_deadline(job, self.x, self.current_mode)
        crit_order = 0 if job.task.criticality == Criticality.HI else 1
        return (eff_deadline, crit_order, job.release_time, job.task.task_id)

    def add_job(self, job: Job) -> None:
        """Add job to ready queue, applying service level scaling for LO tasks in HI mode."""
        if job not in self.ready_queue:
            if self.current_mode == Criticality.HI and job.task.criticality == Criticality.LO:
                if self.degraded_service_level == 0.0:
                    return
                degraded_budget = job.task.C_LO * self.degraded_service_level
                job.required_execution = degraded_budget
                job.remaining_execution = degraded_budget
            self.ready_queue.append(job)

    def remove_job(self, job: Job) -> None:
        """Remove job from ready queue."""
        if job in self.ready_queue:
            self.ready_queue.remove(job)

    def select_job(self, current_time: float) -> Optional[Job]:
        """Select highest priority job from ready queue."""
        if not self.ready_queue:
            return None
        return min(self.ready_queue, key=self._get_priority_key)

    def should_preempt(self, current_job: Optional[Job], candidate_job: Optional[Job]) -> bool:
        """Check if candidate_job should preempt current_job."""
        if current_job is None:
            return True
        if candidate_job is None:
            return False
        return self._get_priority_key(candidate_job) < self._get_priority_key(current_job)
