"""
Risk Score and Mode dynamics plots module.

Generates:
7. Risk Score over Time
8. Mode over Time
9. LO Service Levels over Time
"""

from pathlib import Path
from typing import List, Any
import matplotlib.pyplot as plt


def generate_risk_and_mode_plots(
    risk_history: List[Any],
    service_changes: List[Any],
    output_dir: str = "results/plots",
) -> List[str]:
    """
    Generate plots for risk score, mode state transitions, and service levels over time.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generated_files: List[str] = []

    if not risk_history:
        return generated_files

    timestamps = [rm.timestamp for rm in risk_history]
    risks = [rm.r_total for rm in risk_history]

    # 7. Risk Score Over Time
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(timestamps, risks, color="crimson", linewidth=2.0, label="Risk Score R_total(t)")
    ax.axhline(y=0.50, color="orange", linestyle="--", label="WARNING Threshold (0.50)")
    ax.axhline(y=0.80, color="darkred", linestyle="--", label="HI Threshold (0.80)")
    ax.set_title("7. Proactive Risk Score over Time")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Risk Score")
    ax.set_ylim(0, 1.05)
    ax.grid(True, linestyle=":", alpha=0.6)
    ax.legend(loc="upper right")
    plt.tight_layout()
    f7 = out_path / "7_risk_score_over_time.png"
    plt.savefig(f7, dpi=300)
    plt.close()
    generated_files.append(str(f7))

    # 8. Mode Over Time
    fig, ax = plt.subplots(figsize=(9, 3.5))
    m_times = [0.0]
    m_vals = [0]
    curr_v = 0
    for rm in risk_history:
        m_times.append(rm.timestamp)
        m_vals.append(curr_v)

    ax.step(m_times, m_vals, where="post", color="darkblue", linewidth=2.0)
    ax.set_yticks([0, 1, 2, 3])
    ax.set_yticklabels(["LO", "WARNING", "HI", "RECOVERY"])
    ax.set_title("8. AdaptiveGuard System Mode over Time")
    ax.set_xlabel("Time (ms)")
    ax.set_ylabel("Mode State")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f8 = out_path / "8_mode_over_time.png"
    plt.savefig(f8, dpi=300)
    plt.close()
    generated_files.append(str(f8))

    # 9. LO Service Levels Over Time
    if service_changes:
        fig, ax = plt.subplots(figsize=(9, 4.5))
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
            ax.step(t_pts, s_pts, where="post", label=task_name, color=color, linewidth=1.8)

        ax.set_title("9. LO Task Service Levels over Time")
        ax.set_xlabel("Time (ms)")
        ax.set_ylabel("Service Level")
        ax.set_ylim(-0.05, 1.1)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(loc="lower right")
        plt.tight_layout()
        f9 = out_path / "9_lo_service_levels_over_time.png"
        plt.savefig(f9, dpi=300)
        plt.close()
        generated_files.append(str(f9))

    return generated_files
