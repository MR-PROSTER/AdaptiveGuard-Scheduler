"""
Deadline Metrics Calculator.
"""

from typing import Dict, Any, List
from simulator.task import Criticality


def calculate_deadline_metrics(
    released_jobs: List[Any],
    completed_jobs: List[Any],
    missed_jobs: List[Any],
) -> Dict[str, float]:
    """
    Calculate HI & LO deadline miss ratios and completion statistics.
    """
    hi_released = [j for j in released_jobs if j.task.criticality == Criticality.HI]
    hi_missed = [j for j in missed_jobs if j.task.criticality == Criticality.HI]
    hi_miss_ratio = (len(hi_missed) / len(hi_released)) if hi_released else 0.0

    lo_released = [j for j in released_jobs if j.task.criticality == Criticality.LO]
    lo_completed = [j for j in completed_jobs if j.task.criticality == Criticality.LO]
    lo_missed = [j for j in missed_jobs if j.task.criticality == Criticality.LO]
    lo_completion_ratio = (len(lo_completed) / len(lo_released)) if lo_released else 1.0
    lo_miss_ratio = (len(lo_missed) / len(lo_released)) if lo_released else 0.0

    response_times = [
        j.completion_time - j.release_time
        for j in completed_jobs
        if j.completion_time is not None
    ]
    avg_response_time = (sum(response_times) / len(response_times)) if response_times else 0.0
    worst_response_time = max(response_times) if response_times else 0.0

    return {
        "hi_released_count": float(len(hi_released)),
        "hi_missed_count": float(len(hi_missed)),
        "hi_deadline_miss_ratio": hi_miss_ratio,
        "lo_released_count": float(len(lo_released)),
        "lo_completed_count": float(len(lo_completed)),
        "lo_missed_count": float(len(lo_missed)),
        "lo_completion_ratio": lo_completion_ratio,
        "lo_deadline_miss_ratio": lo_miss_ratio,
        "average_response_time": avg_response_time,
        "worst_response_time": worst_response_time,
    }
