"""
Overhead Metrics Calculator.
"""

from typing import Dict, Any


def calculate_overhead_metrics(
    scheduler_decision_count: int,
    risk_calculation_count: int,
    mode_transition_count: int,
    scheduler_overhead_per_call: float = 0.01,
    risk_overhead_per_call: float = 0.005,
    transition_overhead_per_call: float = 0.01,
    simulation_duration: float = 5000.0,
    enable_overhead: bool = False,
) -> Dict[str, float]:
    """
    Calculate overhead counts, overhead breakdown (ms), and total overhead percentage.
    """
    if not enable_overhead:
        return {
            "scheduler_decision_count": float(scheduler_decision_count),
            "risk_calculation_count": float(risk_calculation_count),
            "mode_transition_count": float(mode_transition_count),
            "scheduler_overhead": 0.0,
            "risk_overhead": 0.0,
            "transition_overhead": 0.0,
            "total_overhead": 0.0,
            "overhead_percentage": 0.0,
        }

    sched_overhead = scheduler_decision_count * scheduler_overhead_per_call
    risk_overhead = risk_calculation_count * risk_overhead_per_call
    trans_overhead = mode_transition_count * transition_overhead_per_call
    total_overhead = sched_overhead + risk_overhead + trans_overhead

    pct = (total_overhead / simulation_duration * 100.0) if simulation_duration > 0 else 0.0

    return {
        "scheduler_decision_count": float(scheduler_decision_count),
        "risk_calculation_count": float(risk_calculation_count),
        "mode_transition_count": float(mode_transition_count),
        "scheduler_overhead": sched_overhead,
        "risk_overhead": risk_overhead,
        "transition_overhead": trans_overhead,
        "total_overhead": total_overhead,
        "overhead_percentage": pct,
    }
