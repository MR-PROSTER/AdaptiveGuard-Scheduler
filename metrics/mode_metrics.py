"""
Mode & Risk Metrics Calculator.
"""

from typing import Dict, Any, List
from controllers.mode_controller import SystemMode


def calculate_mode_metrics(
    risk_history: List[Any],
    mode_transitions: List[Any],
    simulation_duration: float = 5000.0,
) -> Dict[str, float]:
    """
    Calculate mode durations, recovery time, switch count, average risk, and max risk.
    """
    mode_switches_count = len(mode_transitions)
    
    if not risk_history:
        return {
            "mode_switches": float(mode_switches_count),
            "warning_duration": 0.0,
            "hi_duration": 0.0,
            "recovery_duration": 0.0,
            "recovery_time": 0.0,
            "average_risk": 0.0,
            "maximum_risk": 0.0,
        }

    risks = [rm.r_total for rm in risk_history]
    avg_risk = sum(risks) / len(risks)
    max_risk = max(risks)

    # Estimate mode durations from transition timeline
    warning_dur = 0.0
    hi_dur = 0.0
    recovery_dur = 0.0
    first_rec_time = 0.0

    if mode_transitions:
        prev_time = 0.0
        prev_mode = SystemMode.LO

        for tr in mode_transitions:
            dur = max(0.0, tr.time - prev_time)
            if prev_mode == SystemMode.WARNING:
                warning_dur += dur
            elif prev_mode == SystemMode.HI:
                hi_dur += dur
            elif prev_mode == SystemMode.RECOVERY:
                recovery_dur += dur

            if tr.new_mode == SystemMode.RECOVERY and first_rec_time == 0.0:
                first_rec_time = tr.time

            prev_time = tr.time
            prev_mode = tr.new_mode

        # Final interval up to simulation end
        dur = max(0.0, simulation_duration - prev_time)
        if prev_mode == SystemMode.WARNING:
            warning_dur += dur
        elif prev_mode == SystemMode.HI:
            hi_dur += dur
        elif prev_mode == SystemMode.RECOVERY:
            recovery_dur += dur

    return {
        "mode_switches": float(mode_switches_count),
        "warning_duration": warning_dur,
        "hi_duration": hi_dur,
        "recovery_duration": recovery_dur,
        "recovery_time": first_rec_time,
        "average_risk": avg_risk,
        "maximum_risk": max_risk,
    }
