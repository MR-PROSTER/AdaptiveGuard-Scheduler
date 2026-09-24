"""
Runtime Monitor for AdaptiveGuard Discrete-Event Simulator.

Tracks active job execution metrics:
- execution_received (ms)
- remaining_execution (ms)
- absolute_deadline (ms)
- time_to_deadline (ms)
- laxity L_i(t) = D_i - t - R_i(t) (ms)
- C_LO (ms)
- C_HI (ms)
- overrun_status (bool)
"""

from dataclasses import dataclass
from typing import List
from simulator.job import Job
from simulator.task import Criticality


@dataclass
class JobState:
    """
    Tracked runtime state for an active job instance.
    """

    job_id: str
    task_id: int
    task_name: str
    criticality: Criticality
    execution_received: float
    remaining_execution: float
    absolute_deadline: float
    time_to_deadline: float
    laxity: float
    C_LO: float
    C_HI: float
    overrun_status: bool


class RuntimeMonitor:
    """
    Runtime Monitor engine.
    Calculates active job metrics at discrete monitoring checkpoints.
    """

    def __init__(self, monitor_interval: float = 0.5) -> None:
        self.monitor_interval: float = monitor_interval

    def capture_job_state(self, job: Job, current_time: float) -> JobState:
        """
        Compute runtime metrics for a single active job at current_time.

        Laxity formula:
            L_i(t) = D_i - t - R_i(t)

        If laxity < 0, the job is theoretically unable to meet its deadline
        under current allocation.
        """
        execution_received = job.executed_time
        remaining_execution = job.remaining_execution
        absolute_deadline = job.absolute_deadline
        time_to_deadline = absolute_deadline - current_time
        laxity = absolute_deadline - current_time - remaining_execution

        overrun_status = (
            job.task.criticality == Criticality.HI
            and execution_received >= (job.task.C_LO - 1e-9)
            and not job.completed
        )

        return JobState(
            job_id=job.job_id,
            task_id=job.task.task_id,
            task_name=job.task.name,
            criticality=job.task.criticality,
            execution_received=execution_received,
            remaining_execution=remaining_execution,
            absolute_deadline=absolute_deadline,
            time_to_deadline=time_to_deadline,
            laxity=laxity,
            C_LO=job.task.C_LO,
            C_HI=job.task.C_HI,
            overrun_status=overrun_status,
        )

    def monitor_active_jobs(
        self, active_jobs: List[Job], current_time: float
    ) -> List[JobState]:
        """
        Snapshot metrics for all currently active jobs.
        """
        return [self.capture_job_state(job, current_time) for job in active_jobs if not job.completed]
