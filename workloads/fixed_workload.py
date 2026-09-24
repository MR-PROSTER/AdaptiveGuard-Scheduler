from typing import List
from simulator.task import Task, Criticality


def get_fixed_workload() -> List[Task]:
    """
    Generate a benchmark mixed-criticality taskset.

    Rules applied:
    - HI tasks satisfy C_LO < C_HI
    - LO tasks satisfy C_LO == C_HI
    - Primary experiments satisfy relative_deadline D_i == period T_i
    """
    return [
        Task(
            task_id=1,
            name="FlightControl_HI",
            criticality=Criticality.HI,
            period=10.0,
            relative_deadline=10.0,
            C_LO=2.0,
            C_HI=4.0,
            utility=1.0,
            minimum_service=0.5,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=2,
            name="Telemetry_LO",
            criticality=Criticality.LO,
            period=20.0,
            relative_deadline=20.0,
            C_LO=3.0,
            C_HI=3.0,
            utility=0.5,
            minimum_service=0.0,
            maximum_service=1.0,
            release_offset=0.0,
        ),
        Task(
            task_id=3,
            name="SensorFusion_HI",
            criticality=Criticality.HI,
            period=25.0,
            relative_deadline=25.0,
            C_LO=4.0,
            C_HI=8.0,
            utility=0.9,
            minimum_service=0.4,
            maximum_service=1.0,
            release_offset=5.0,
        ),
    ]
