"""
Earliest Deadline First with Virtual Deadlines (EDF-VD) Scheduler.

Extends standard EDF for Mixed-Criticality systems by scaling deadlines of
HI-criticality tasks during LO mode using a dynamic scaling factor x.

Formula:
  x = U_HI_LO / (1 - U_LO)

Virtual Deadline in LO mode for HI tasks:
  d'_i = release_time + x * (D_i - release_time)
"""

from typing import List, Optional, Tuple, Union
from simulator.job import Job
from simulator.task import Task, Criticality
from schedulers.base_scheduler import BaseScheduler


def calculate_x(tasks: List[Task]) -> float:
    """
    Calculate the EDF-VD deadline scaling factor x dynamically from the task set.

    Formula:
        x = U_HI_LO / (1 - U_LO)

    Where:
        U_HI_LO = sum(C_LO / T) for HI-criticality tasks
        U_LO    = sum(C_LO / T) for LO-criticality tasks
    """
    u_hi_lo = sum(t.C_LO / t.period for t in tasks if t.criticality == Criticality.HI)
    u_lo = sum(t.C_LO / t.period for t in tasks if t.criticality == Criticality.LO)

    if u_lo >= 1.0 - 1e-6:
        return 1.0

    return min(1.0, max(0.0, u_hi_lo / (1.0 - u_lo)))


def virtual_deadline(
    job: Job,
    x: float,
    current_mode: Criticality = Criticality.LO,
) -> float:
    """
    Calculate the effective deadline for a job given scaling factor x and current system mode.

    Rules:
      - HI jobs use virtual deadlines while in LO mode: release_time + x * (absolute_deadline - release_time)
      - LO jobs use their actual deadlines
      - In HI mode, HI tasks use their actual deadlines
    """
    if current_mode == Criticality.LO and job.task.criticality == Criticality.HI:
        return job.release_time + x * (job.absolute_deadline - job.release_time)
    return job.absolute_deadline


class EDFVDScheduler(BaseScheduler):
    """
    EDF with Virtual Deadlines (EDF-VD) Scheduler.

    Attributes:
        tasks (List[Task]): Workload taskset.
        x (float): Dynamic scaling factor calculated from taskset.
        current_mode (Criticality): Current system criticality mode (LO or HI).
    """

    def __init__(
        self,
        tasks: Optional[List[Task]] = None,
        x: Optional[float] = None,
        initial_mode: Criticality = Criticality.LO,
    ) -> None:
        super().__init__(name="EDF-VD")
        self.current_mode: Criticality = initial_mode
        self.tasks: List[Task] = tasks or []

        if x is not None:
            self.x: float = x
        elif self.tasks:
            self.x = calculate_x(self.tasks)
        else:
            self.x = 1.0

    def set_mode(self, new_mode: Criticality) -> None:
        """Switch current system criticality mode."""
        if self.current_mode != new_mode:
            self.current_mode = new_mode
            if new_mode == Criticality.HI:
                # In standard EDF-VD, upon transition to HI mode, LO tasks are dropped from ready queue
                self.ready_queue = [
                    job for job in self.ready_queue if job.task.criticality == Criticality.HI
                ]

    def _get_priority_key(self, job: Job) -> Tuple[float, int, float, int]:
        """
        Construct priority comparison key using virtual_deadline in LO mode for HI tasks.
        """
        eff_deadline = virtual_deadline(job, self.x, self.current_mode)
        crit_order = 0 if job.task.criticality == Criticality.HI else 1
        return (eff_deadline, crit_order, job.release_time, job.task.task_id)

    def add_job(self, job: Job) -> None:
        """Add job to ready queue if not already present."""
        if job not in self.ready_queue:
            # If in HI mode, drop incoming LO jobs
            if self.current_mode == Criticality.HI and job.task.criticality == Criticality.LO:
                return
            self.ready_queue.append(job)

    def remove_job(self, job: Job) -> None:
        """Remove job from ready queue."""
        if job in self.ready_queue:
            self.ready_queue.remove(job)

    def select_job(self, current_time: float) -> Optional[Job]:
        """Select highest priority job from ready queue based on effective deadlines."""
        if not self.ready_queue:
            return None
        return min(self.ready_queue, key=self._get_priority_key)

    def should_preempt(self, current_job: Optional[Job], candidate_job: Optional[Job]) -> bool:
        """Determine if candidate_job has strictly earlier effective deadline than current_job."""
        if current_job is None:
            return True
        if candidate_job is None:
            return False
        return self._get_priority_key(candidate_job) < self._get_priority_key(current_job)
