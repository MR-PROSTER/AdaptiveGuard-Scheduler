from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.task import Task


@dataclass
class Job:
    """
    Job Model representing an individual job instance released by a Task.

    Attributes:
        job_id (str): Unique job identifier (e.g., 'T1_J0').
        task (Task): Reference to the parent Task.
        release_time (float): Absolute release time r_i,k = offset + k * period.
        absolute_deadline (float): Absolute deadline d_i,k = release_time + relative_deadline.
        required_execution (float): Total execution time required for this job instance.
        remaining_execution (float): Execution time remaining to finish the job.
        sequence_num (int): Job sequence index k (0, 1, 2, ...).
        executed_time (float): Accumulated execution time spent on CPU.
        start_time (Optional[float]): Time when job first started execution.
        completion_time (Optional[float]): Time when job completed execution.
        completed (bool): Flag indicating if job successfully completed.
        missed_deadline (bool): Flag indicating if job missed its deadline.
    """

    job_id: str
    task: "Task"
    release_time: float
    absolute_deadline: float
    required_execution: float
    remaining_execution: float
    sequence_num: int = 0
    executed_time: float = 0.0
    start_time: Optional[float] = None
    completion_time: Optional[float] = None
    completed: bool = False
    missed_deadline: bool = False

    def execute(self, duration: float) -> float:
        """
        Execute the job for up to `duration` time units.

        Args:
            duration (float): Maximum execution duration offered by CPU.

        Returns:
            float: Actual execution time consumed by the job.
        """
        if self.completed or duration <= 0:
            return 0.0

        actual_exec = min(duration, self.remaining_execution)
        self.executed_time += actual_exec
        self.remaining_execution -= actual_exec

        if self.remaining_execution <= 1e-9:
            self.remaining_execution = 0.0
            self.completed = True

        return actual_exec

    def check_deadline(self, current_time: float) -> bool:
        """
        Check if the job has missed its deadline at `current_time`.

        Returns:
            bool: True if deadline is missed, False otherwise.
        """
        if not self.completed and current_time > self.absolute_deadline:
            self.missed_deadline = True
            return True
        return False
