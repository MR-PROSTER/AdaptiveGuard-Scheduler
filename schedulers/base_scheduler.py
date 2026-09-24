from abc import ABC, abstractmethod
from typing import List, Optional
from simulator.job import Job


class BaseScheduler(ABC):
    """
    Abstract Base Class for Mixed-Criticality Real-Time Schedulers.

    Defines the standard interface for job queue management, priority evaluation,
    preemption logic, and scheduling lifecycle hooks.
    """

    def __init__(self, name: str = "BaseScheduler") -> None:
        self.name: str = name
        self.ready_queue: List[Job] = []

    @abstractmethod
    def add_job(self, job: Job) -> None:
        """Add a newly released or preempted job to the ready queue."""
        pass

    @abstractmethod
    def remove_job(self, job: Job) -> None:
        """Remove a job from the ready queue."""
        pass

    @abstractmethod
    def select_job(self, current_time: float) -> Optional[Job]:
        """Select the highest-priority job from the ready queue for execution."""
        pass

    @abstractmethod
    def should_preempt(self, current_job: Job, candidate_job: Job) -> bool:
        """
        Determine whether candidate_job has strictly higher priority than current_job
        and should preempt it.
        """
        pass

    def on_job_release(self, job: Job) -> None:
        """Hook triggered when a job is released into the system."""
        self.add_job(job)

    def on_job_completion(self, job: Job) -> None:
        """Hook triggered when a job completes execution."""
        self.remove_job(job)
