"""
AdaptiveGuard Scheduler.

Integrates:
1. Earliest Deadline First with Virtual Deadlines (EDF-VD)
2. Runtime Monitoring & Laxity / Overrun tracking
3. Proactive Risk Estimation
4. Dynamic Mode Transitions with Hysteresis (LO -> WARNING -> HI -> RECOVERY)
5. Utility-Aware LO Task Degradation (Ranking by utility density)
6. Gradual LO Task Recovery (Step-by-step restoration: 0.00 -> 0.25 -> 0.50 -> 0.75 -> 1.00)

Complete Control Loop:
    Job execution -> Runtime Monitor -> Risk Estimator -> Mode Controller -> Degradation Controller -> EDF-VD Scheduler -> CPU -> repeat
"""

from typing import List, Optional, Tuple
from simulator.job import Job
from simulator.task import Task, Criticality
from schedulers.base_scheduler import BaseScheduler
from schedulers.edf_vd import calculate_x, virtual_deadline
from controllers.mode_controller import SystemMode


class AdaptiveGuardScheduler(BaseScheduler):
    """
    Complete AdaptiveGuard Scheduler engine.
    """

    def __init__(
        self,
        tasks: Optional[List[Task]] = None,
        x: Optional[float] = None,
        initial_mode: SystemMode = SystemMode.LO,
    ) -> None:
        super().__init__(name="AdaptiveGuard")
        self.tasks: List[Task] = tasks or []
        self.current_mode: SystemMode = initial_mode

        if x is not None:
            self.x: float = x
        elif self.tasks:
            self.x = calculate_x(self.tasks)
        else:
            self.x = 1.0

        self.ready_queue: List[Job] = []

    def set_mode(self, new_mode: SystemMode) -> None:
        """Update active system mode."""
        self.current_mode = new_mode

    def _get_effective_deadline(self, job: Job) -> float:
        """
        Calculate effective deadline for job:
        - In LO or WARNING mode: HI tasks use virtual deadline d'_i.
        - In HI or RECOVERY mode: HI tasks revert to actual deadline.
        - LO tasks always use actual deadline.
        """
        if self.current_mode in (SystemMode.LO, SystemMode.WARNING) and job.task.criticality == Criticality.HI:
            return virtual_deadline(job, self.x, Criticality.LO)
        return job.absolute_deadline

    def add_job(self, job: Job) -> None:
        """Add job to ready queue if not already present."""
        if job not in self.ready_queue and not job.completed:
            self.ready_queue.append(job)

    def remove_job(self, job: Job) -> None:
        """Remove job from ready queue."""
        if job in self.ready_queue:
            self.ready_queue.remove(job)

    def select_job(self, current_time: float) -> Optional[Job]:
        """
        Select highest-priority job from ready queue.

        Priority Order:
          1. Smallest effective deadline
          2. HI criticality first
          3. Earlier release time
          4. Task ID
        """
        active_ready = [j for j in self.ready_queue if not j.completed]
        if not active_ready:
            return None

        return min(
            active_ready,
            key=lambda j: (
                self._get_effective_deadline(j),
                0 if j.task.criticality == Criticality.HI else 1,
                j.release_time,
                j.task.task_id,
            ),
        )

    def should_preempt(self, current_job: Job, candidate_job: Job) -> bool:
        """
        Determine whether candidate job should preempt current job.
        """
        if current_job == candidate_job:
            return False

        current_eff = self._get_effective_deadline(current_job)
        candidate_eff = self._get_effective_deadline(candidate_job)

        current_key = (
            current_eff,
            0 if current_job.task.criticality == Criticality.HI else 1,
            current_job.release_time,
            current_job.task.task_id,
        )
        candidate_key = (
            candidate_eff,
            0 if candidate_job.task.criticality == Criticality.HI else 1,
            candidate_job.release_time,
            candidate_job.task.task_id,
        )

        return candidate_key < current_key

    def on_job_release(self, job: Job) -> None:
        """Handle job release event."""
        self.add_job(job)

    def on_job_completion(self, job: Job) -> None:
        """Handle job completion event."""
        self.remove_job(job)
