"""
Timeline Visualization Module for stress_20ms Benchmark Workload.

Plots:
- Time vs Running Task
- Time vs System Mode
- Time vs Total Risk Score
- Time vs LO Task Service Levels
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import matplotlib.pyplot as plt


def plot_stress_20ms_timeline(
    timeline: List[Any],
    risk_history: List[Any],
    service_changes: List[Any],
    output_dir: str = "results/plots",
    filename: str = "stress_20ms_timeline.png",
) -> str:
    """
    Generate combined timeline plot for stress_20ms workload.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    full_file = out_path / filename

    fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

    # 1. Risk Score over time
    if risk_history:
        timestamps = [rm.timestamp for rm in risk_history]
        risks = [rm.r_total for rm in risk_history]
        axes[0].plot(timestamps, risks, color="crimson", linewidth=2.0, label="Risk Score (R_total)")
        axes[0].axhline(y=0.50, color="orange", linestyle="--", label="WARNING Threshold (0.50)")
        axes[0].axhline(y=0.80, color="darkred", linestyle="--", label="HI Threshold (0.80)")
        axes[0].axhline(y=0.40, color="green", linestyle=":", label="RECOVERY Threshold (0.40)")
        axes[0].set_ylabel("Risk Score")
        axes[0].set_ylim(0, 1.05)
        axes[0].grid(True, linestyle=":", alpha=0.6)
        axes[0].legend(loc="upper right")
        axes[0].set_title("AdaptiveGuard Control Loop Dynamics (stress_20ms)")

    # 2. Service Levels over time
    if service_changes:
        tasks_seen = sorted(list({sc.task_name for sc in service_changes}))
        colors = ["navy", "teal", "darkgreen", "purple", "darkorange"]

        for idx, task_name in enumerate(tasks_seen):
            t_pts = [0.0]
            s_pts = [1.00]

            for sc in service_changes:
                if sc.task_name == task_name:
                    t_pts.append(sc.time)
                    s_pts.append(sc.old_service)
                    t_pts.append(sc.time)
                    s_pts.append(sc.new_service)

            color = colors[idx % len(colors)]
            axes[1].step(t_pts, s_pts, where="post", label=f"{task_name}", color=color, linewidth=1.8)

        axes[1].set_ylabel("LO Service Level")
        axes[1].set_ylim(-0.05, 1.1)
        axes[1].grid(True, linestyle=":", alpha=0.6)
        axes[1].legend(loc="lower right")

    # 3. Mode over time
    if risk_history:
        mode_map = {"LO": 0, "WARNING": 1, "HI": 2, "RECOVERY": 3}
        # Step plot for modes
        m_times = [0.0]
        m_vals = [0]

        curr_val = 0
        for rm in risk_history:
            m_times.append(rm.timestamp)
            m_vals.append(curr_val)

        axes[2].step(m_times, m_vals, where="post", color="darkblue", linewidth=2.0)
        axes[2].set_yticks([0, 1, 2, 3])
        axes[2].set_yticklabels(["LO", "WARNING", "HI", "RECOVERY"])
        axes[2].set_ylabel("System Mode")
        axes[2].set_xlabel("Time (ms)")
        axes[2].grid(True, linestyle=":", alpha=0.6)

    plt.tight_layout()
    plt.savefig(full_file, dpi=300)
    plt.close()

    return str(full_file)
