"""
Fixed Demonstration Workload: stress_20ms

This workload defines a mixed-criticality taskset with 2 HI tasks and 4 LO tasks
sharing a uniform period and deadline of 20ms.

Calculated Utilizations:
- HI LO-assumption utilization: 2/20 + 3/20 = 0.25
- LO utilization: (6+1+1+1)/20 = 0.45
- Normal total utilization: 0.70
- Worst-case total utilization: (6+7+6+1+1+1)/20 = 1.10

The workload is intentionally normal-load feasible (0.70 <= 1.0)
but worst-case overloaded (1.10 > 1.0).
"""

from enum import Enum
import random
from typing import List, Union, Optional

from simulator.task import Task, Criticality

WORKLOAD_NAME = "stress_20ms"


class ExecutionScenario(Enum):
    NORMAL = "NORMAL"
    H1_OVERRUN = "H1_OVERRUN"
    BOTH_OVERRUN = "BOTH_OVERRUN"
    BURSTY = "BURSTY"
    RECOVERY = "RECOVERY"


def get_stress_20ms_workload() -> List[Task]:
    """
    Generate the 'stress_20ms' fixed benchmark workload.

    Taskset composition (T = 20ms, D = 20ms for all tasks):
      - H1: Flight_Control  (HI, C_LO=2ms, C_HI=6ms, utility=0, min_service=1.0, max_service=1.0)
      - H2: Braking_Control (HI, C_LO=3ms, C_HI=7ms, utility=0, min_service=1.0, max_service=1.0)
      - L1: Telemetry       (LO, C_LO=6ms, C_HI=6ms, utility=100, min_service=0.0, max_service=1.0)
      - L2: Logging_A       (LO, C_LO=1ms, C_HI=1ms, utility=10, min_service=0.0, max_service=1.0)
      - L3: Logging_B       (LO, C_LO=1ms, C_HI=1ms, utility=10, min_service=0.0, max_service=1.0)
      - L4: Logging_C       (LO, C_LO=1ms, C_HI=1ms, utility=10, min_service=0.0, max_service=1.0)
    """
    return [
        Task(
            task_id=1,
            name="Flight_Control",
            criticality=Criticality.HI,
            period=20.0,
            relative_deadline=20.0,
            C_LO=2.0,
            C_HI=6.0,
            utility=0.0,
            minimum_service=1.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=2,
            name="Braking_Control",
            criticality=Criticality.HI,
            period=20.0,
            relative_deadline=20.0,
            C_LO=3.0,
            C_HI=7.0,
            utility=0.0,
            minimum_service=1.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=3,
            name="Telemetry",
            criticality=Criticality.LO,
            period=20.0,
            relative_deadline=20.0,
            C_LO=6.0,
            C_HI=6.0,
            utility=100.0,
            minimum_service=0.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=4,
            name="Logging_A",
            criticality=Criticality.LO,
            period=20.0,
            relative_deadline=20.0,
            C_LO=1.0,
            C_HI=1.0,
            utility=10.0,
            minimum_service=0.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=5,
            name="Logging_B",
            criticality=Criticality.LO,
            period=20.0,
            relative_deadline=20.0,
            C_LO=1.0,
            C_HI=1.0,
            utility=10.0,
            minimum_service=0.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=6,
            name="Logging_C",
            criticality=Criticality.LO,
            period=20.0,
            relative_deadline=20.0,
            C_LO=1.0,
            C_HI=1.0,
            utility=10.0,
            minimum_service=0.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
    ]


def get_fixed_workload() -> List[Task]:
    """Alias for get_stress_20ms_workload to maintain backwards compatibility."""
    return get_stress_20ms_workload()


def calculate_hi_lo_utilization(tasks: List[Task]) -> float:
    """Calculate HI tasks LO-assumption utilization: sum(C_LO / T) for HI tasks."""
    return sum(t.C_LO / t.period for t in tasks if t.criticality == Criticality.HI)


def calculate_lo_utilization(tasks: List[Task]) -> float:
    """Calculate LO tasks utilization: sum(C_LO / T) for LO tasks."""
    return sum(t.C_LO / t.period for t in tasks if t.criticality == Criticality.LO)


def calculate_normal_utilization(tasks: List[Task]) -> float:
    """Calculate Normal total utilization: sum(C_LO / T) for all tasks."""
    return sum(t.C_LO / t.period for t in tasks)


def calculate_worst_case_utilization(tasks: List[Task]) -> float:
    """
    Calculate Worst-case total utilization:
    sum(C_HI / T) for HI tasks + sum(C_LO / T) for LO tasks.
    """
    return sum(
        (t.C_HI if t.criticality == Criticality.HI else t.C_LO) / t.period
        for t in tasks
    )


def print_workload_utilization(tasks: Optional[List[Task]] = None) -> None:
    """Print the calculated utilization metrics for the workload."""
    if tasks is None:
        tasks = get_stress_20ms_workload()

    hi_lo_util = calculate_hi_lo_utilization(tasks)
    lo_util = calculate_lo_utilization(tasks)
    normal_util = calculate_normal_utilization(tasks)
    worst_case_util = calculate_worst_case_utilization(tasks)

    print("HI LO-assumption utilization:")
    print(f"  2/20 + 3/20 = {hi_lo_util:.2f}")
    print()
    print("LO utilization:")
    print(f"  (6+1+1+1)/20 = {lo_util:.2f}")
    print()
    print("Normal total utilization:")
    print(f"  {normal_util:.2f}")
    print()
    print("Worst-case total utilization:")
    print(f"  (6+7+6+1+1+1)/20 = {worst_case_util:.2f}")
    print()
    print("The workload is intentionally normal-load feasible but worst-case overloaded.")


def get_job_execution_requirement(
    task: Task,
    sequence_num: int,
    scenario: Union[ExecutionScenario, str] = ExecutionScenario.NORMAL,
    seed: int = 42,
    overload_until_seq: int = 3,
) -> float:
    """
    Determine execution requirement for a specific job instance of a task under a given scenario.

    Scenarios:
      1. NORMAL: H1 requires C_LO, H2 requires C_LO
      2. H1_OVERRUN: H1 requires C_HI, H2 requires C_LO
      3. BOTH_OVERRUN: H1 requires C_HI, H2 requires C_HI
      4. BURSTY: Randomly select intervals where HI tasks require C_HI (fixed random seed)
      5. RECOVERY: Initially create an overloaded period (seq < overload_until_seq), then return HI tasks to C_LO
    """
    if isinstance(scenario, str):
        scenario = ExecutionScenario(scenario)

    if scenario == ExecutionScenario.NORMAL:
        return task.C_LO

    elif scenario == ExecutionScenario.H1_OVERRUN:
        if task.criticality == Criticality.HI and (task.name == "Flight_Control" or task.task_id == 1):
            return task.C_HI
        return task.C_LO

    elif scenario == ExecutionScenario.BOTH_OVERRUN:
        if task.criticality == Criticality.HI:
            return task.C_HI
        return task.C_LO

    elif scenario == ExecutionScenario.BURSTY:
        if task.criticality == Criticality.HI:
            rng = random.Random(seed + task.task_id * 1000 + sequence_num)
            return task.C_HI if rng.random() < 0.5 else task.C_LO
        return task.C_LO

    elif scenario == ExecutionScenario.RECOVERY:
        if task.criticality == Criticality.HI:
            if sequence_num < overload_until_seq:
                return task.C_HI
            else:
                return task.C_LO
        return task.C_LO

    return task.C_LO
