from typing import Optional
from simulator.job import Job


class CPU:
    """
    Single-core CPU model.

    Attributes:
        speed (float): Processing speed factor (default: 1.0).
        current_job (Optional[Job]): Currently executing job instance.
        total_busy_time (float): Accumulated CPU busy time (ms).
        total_idle_time (float): Accumulated CPU idle time (ms).
    """

    def __init__(self, speed: float = 1.0) -> None:
        self.speed: float = speed
        self.current_job: Optional[Job] = None
        self.total_busy_time: float = 0.0
        self.total_idle_time: float = 0.0
        self._last_state_change_time: float = 0.0

    def is_idle(self) -> bool:
        """Check if CPU is idle."""
        return self.current_job is None

    def assign_job(self, job: Job, current_time: float) -> None:
        """Assign a job to start running on the CPU."""
        if self.is_idle():
            self.total_idle_time += current_time - self._last_state_change_time
            self._last_state_change_time = current_time

        self.current_job = job
        if job.start_time is None:
            job.start_time = current_time

    def execute(self, duration: float, current_time: float) -> float:
        """
        Execute the assigned job for up to duration ms scaled by CPU speed.

        Args:
            duration (float): Time duration offered for execution.
            current_time (float): Current simulation time.

        Returns:
            float: Actual execution time performed.
        """
        if self.current_job is None or duration <= 0:
            return 0.0

        effective_duration = duration * self.speed
        actual_exec = self.current_job.execute(effective_duration)
        self.total_busy_time += actual_exec
        return actual_exec

    def preempt(self, current_time: float) -> Optional[Job]:
        """
        Preempt current running job and yield CPU.

        Returns:
            Optional[Job]: The job that was preempted, or None if CPU was idle.
        """
        preempted_job = self.current_job
        self.current_job = None
        self._last_state_change_time = current_time
        return preempted_job

    def set_idle(self, current_time: float) -> None:
        """Set CPU state to idle."""
        self.current_job = None
        self._last_state_change_time = current_time
