"""
Classical Reactive MC Scheduler.

A simplified baseline based on the classical mixed-criticality mode-switch model.
(Note: This is a simplified baseline model, not Vestal's exact implementation).

Lifecycle:
- Initial mode: LO
- When a HI job executes beyond C_LO before completing:
  Transition LO -> HI.
- In HI mode:
  - HI tasks are protected and execute using C_HI budget and actual deadlines.
  - LO tasks are suspended/dropped.
"""

from typing import List, Optional, Tuple
from simulator.job import Job
from simulator.task import Criticality
from schedulers.base_scheduler import BaseScheduler


class ClassicalReactiveMCScheduler(BaseScheduler):
    """
    Classical Reactive MC Baseline Scheduler.

    A simplified baseline based on the classical mixed-criticality mode-switch model.
    """

    def __init__(self, initial_mode: Criticality = Criticality.LO) -> None:
        super().__init__(name="Classical Reactive MC")
        self.current_mode: Criticality = initial_mode

    def set_mode(self, new_mode: Criticality) -> None:
        """Handle global mode switch LO -> HI."""
        if self.current_mode != new_mode:
            self.current_mode = new_mode
            if new_mode == Criticality.HI:
                # Suspend/drop all LO tasks from ready queue upon mode switch
                self.ready_queue = [
                    job for job in self.ready_queue if job.task.criticality == Criticality.HI
                ]

    def _get_priority_key(self, job: Job) -> Tuple[float, int, float, int]:
        """Standard EDF priority key based on actual deadlines."""
        crit_order = 0 if job.task.criticality == Criticality.HI else 1
        return (job.absolute_deadline, crit_order, job.release_time, job.task.task_id)

    def add_job(self, job: Job) -> None:
        """Add job to ready queue, dropping LO jobs if in HI mode."""
        if job not in self.ready_queue:
            if self.current_mode == Criticality.HI and job.task.criticality == Criticality.LO:
                return
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
        """Determine if candidate_job has strictly higher priority than current_job."""
        if current_job is None:
            return True
        if candidate_job is None:
            return False
        return self._get_priority_key(candidate_job) < self._get_priority_key(current_job)
