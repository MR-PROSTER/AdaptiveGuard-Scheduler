"""
Flexible MC Scheduler.

Implements task/job-level criticality escalation.

Key Rules:
- When HI task H1 overruns C_LO, H1 escalates independently to C_HI behavior (actual deadline D_i).
- HI task H2 does NOT automatically escalate when H1 overruns.
- H2 continues using C_LO (and virtual deadline if in LO mode) until H2 itself overruns.
- If H2 later overruns, H2 escalates independently.
- This baseline does NOT automatically switch every HI task into HI behavior.
"""

from typing import List, Optional, Set, Tuple
from simulator.job import Job
from simulator.task import Task, Criticality
from schedulers.base_scheduler import BaseScheduler
from schedulers.edf_vd import calculate_x


class FlexibleMCScheduler(BaseScheduler):
    """
    Flexible MC Baseline Scheduler.

    Escalates task behavior on a per-task/per-job basis upon overrun, rather than
    globally switching all HI tasks into HI behavior.
    """

    def __init__(
        self,
        tasks: Optional[List[Task]] = None,
        x: Optional[float] = None,
    ) -> None:
        super().__init__(name="Flexible MC")
        self.tasks: List[Task] = tasks or []

        if x is not None:
            self.x: float = x
        elif self.tasks:
            self.x = calculate_x(self.tasks)
        else:
            self.x = 1.0

        # Set of task_ids for tasks that have independently escalated
        self.escalated_tasks: Set[int] = set()

    def on_task_overrun(self, task: Task) -> None:
        """Escalate only the specific task that overran C_LO."""
        self.escalated_tasks.add(task.task_id)

    def is_task_escalated(self, task: Task) -> bool:
        """Check if a specific task has escalated."""
        return task.task_id in self.escalated_tasks

    def _get_effective_deadline(self, job: Job) -> float:
        """
        Calculate effective deadline:
        - Escalated HI tasks use actual deadline.
        - Non-escalated HI tasks use virtual deadline.
        - LO tasks use actual deadline.
        """
        if job.task.criticality == Criticality.HI:
            if self.is_task_escalated(job.task):
                return job.absolute_deadline
            else:
                return job.release_time + self.x * (job.absolute_deadline - job.release_time)
        return job.absolute_deadline

    def _get_priority_key(self, job: Job) -> Tuple[float, int, float, int]:
        """Construct priority key using task-level effective deadline."""
        eff_deadline = self._get_effective_deadline(job)
        crit_order = 0 if job.task.criticality == Criticality.HI else 1
        return (eff_deadline, crit_order, job.release_time, job.task.task_id)

    def add_job(self, job: Job) -> None:
        """Add job to ready queue."""
        if job not in self.ready_queue:
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
