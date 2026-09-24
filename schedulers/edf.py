from typing import List, Optional, Tuple
from simulator.job import Job
from simulator.task import Criticality
from schedulers.base_scheduler import BaseScheduler


class EDFScheduler(BaseScheduler):
    """
    Standard Earliest Deadline First (EDF) Scheduler.

    Priority evaluation rules (lower tuple value = higher priority):
      1. Smallest absolute deadline (job.absolute_deadline)
      2. HI criticality first (Criticality.HI before Criticality.LO)
      3. Earlier release time (job.release_time)
      4. Smaller Task ID (job.task.task_id)

    Deadlines are never altered under standard EDF.
    """

    def __init__(self) -> None:
        super().__init__(name="EDF")

    def _get_priority_key(self, job: Job) -> Tuple[float, int, float, int]:
        """
        Construct priority comparison key for a job under EDF.

        Tie-breaking criteria:
          1. absolute_deadline (float)
          2. criticality (0 for HI, 1 for LO)
          3. release_time (float)
          4. task_id (int)
        """
        crit_order = 0 if job.task.criticality == Criticality.HI else 1
        return (job.absolute_deadline, crit_order, job.release_time, job.task.task_id)

    def add_job(self, job: Job) -> None:
        """Add job to ready queue if not already present."""
        if job not in self.ready_queue:
            self.ready_queue.append(job)

    def remove_job(self, job: Job) -> None:
        """Remove job from ready queue."""
        if job in self.ready_queue:
            self.ready_queue.remove(job)

    def select_job(self, current_time: float) -> Optional[Job]:
        """
        Select the job with highest priority (smallest priority key) from ready queue.
        """
        if not self.ready_queue:
            return None
        return min(self.ready_queue, key=self._get_priority_key)

    def should_preempt(self, current_job: Optional[Job], candidate_job: Optional[Job]) -> bool:
        """
        Check if candidate_job has strictly higher priority than current_job.
        """
        if current_job is None:
            return True
        if candidate_job is None:
            return False
        return self._get_priority_key(candidate_job) < self._get_priority_key(current_job)
