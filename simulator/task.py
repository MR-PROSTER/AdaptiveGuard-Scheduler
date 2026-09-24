from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.job import Job


class Criticality(Enum):
    LO = "LO"
    HI = "HI"


@dataclass
class Task:
    """
    Mixed-Criticality Task Model.

    Attributes:
        task_id (int): Unique identifier for the task.
        name (str): Human-readable task name.
        criticality (Criticality): Criticality level (HI or LO).
        period (float): Task period T_i (ms).
        relative_deadline (float): Task relative deadline D_i (ms).
        C_LO (float): Worst-case execution time in LO criticality mode (ms).
        C_HI (float): Worst-case execution time in HI criticality mode (ms).
        utility (float): Task utility contribution (default: 1.0).
        minimum_service (float): Minimum service level required (default: 0.0).
        maximum_service (float): Maximum service level required (default: 1.0).
        release_offset (float): Release offset time (ms, default: 0.0).
    """

    task_id: int
    name: str
    criticality: Criticality
    period: float
    relative_deadline: float
    C_LO: float
    C_HI: float
    utility: float = 1.0
    minimum_service: float = 0.0
    maximum_service: float = 1.0
    release_offset: float = 0.0

    def __post_init__(self) -> None:
        """Validate mixed-criticality constraints."""
        if self.period <= 0:
            raise ValueError(f"Task period must be positive, got {self.period}")
        if self.relative_deadline <= 0:
            raise ValueError(
                f"Task relative deadline must be positive, got {self.relative_deadline}"
            )
        if self.C_LO <= 0:
            raise ValueError(f"Task C_LO must be positive, got {self.C_LO}")
        if self.C_HI <= 0:
            raise ValueError(f"Task C_HI must be positive, got {self.C_HI}")
        if self.release_offset < 0:
            raise ValueError(
                f"Release offset must be non-negative, got {self.release_offset}"
            )

        # Enforce Mixed-Criticality rules:
        if self.criticality == Criticality.HI:
            if not (self.C_LO < self.C_HI):
                raise ValueError(
                    f"HI task '{self.name}' violation: C_LO ({self.C_LO}) must be strictly less than C_HI ({self.C_HI})."
                )
        elif self.criticality == Criticality.LO:
            if not (self.C_LO == self.C_HI):
                raise ValueError(
                    f"LO task '{self.name}' violation: C_LO ({self.C_LO}) must equal C_HI ({self.C_HI})."
                )

    def generate_job(self, sequence_num: int, execution_budget: float | None = None) -> "Job":
        """
        Generate job instance k for this task.

        Formula:
            release_time = offset + sequence_num * period
            absolute_deadline = release_time + relative_deadline
        """
        from simulator.job import Job

        release_time = self.release_offset + sequence_num * self.period
        absolute_deadline = release_time + self.relative_deadline
        required_exec = execution_budget if execution_budget is not None else self.C_LO
        job_id = f"T{self.task_id}_J{sequence_num}"

        return Job(
            job_id=job_id,
            task=self,
            release_time=release_time,
            absolute_deadline=absolute_deadline,
            required_execution=required_exec,
            remaining_execution=required_exec,
            sequence_num=sequence_num,
        )
