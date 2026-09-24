"""
Utility Metrics Calculator.
"""

from typing import Dict, Any, List
from simulator.task import Task, Criticality


def calculate_utility_metrics(
    tasks: List[Task],
    completed_jobs: List[Any],
    released_jobs: List[Any],
) -> Dict[str, float]:
    """
    Calculate LO utility, max LO utility, and LO utility preservation ratio.
    """
    lo_tasks = [t for t in tasks if t.criticality == Criticality.LO]
    max_utility = sum(t.utility for t in lo_tasks)

    lo_utility = 0.0
    for task in lo_tasks:
        task_released = [j for j in released_jobs if j.task.task_id == task.task_id]
        task_completed = [j for j in completed_jobs if j.task.task_id == task.task_id]

        if not task_released:
            service_fraction = 1.0
        else:
            exec_sum = sum(j.executed_time for j in task_completed)
            req_sum = sum(j.required_execution for j in task_released)
            service_fraction = (exec_sum / req_sum) if req_sum > 0 else 0.0

        lo_utility += task.utility * service_fraction

    ratio = (lo_utility / max_utility) if max_utility > 0 else 1.0

    return {
        "LO_utility": lo_utility,
        "maximum_possible_LO_utility": max_utility,
        "LO_utility_preservation_ratio": ratio,
        "LO_utility_ratio": ratio,
    }
