"""
Utility and Monitoring Interval Plots Module.

Generates:
10. Monitoring Interval vs Overhead
11. Monitoring Interval vs LO Utility
"""

from pathlib import Path
from typing import List
import matplotlib.pyplot as plt
import pandas as pd


def generate_utility_and_monitoring_plots(
    df: pd.DataFrame,
    output_dir: str = "results/plots",
) -> List[str]:
    """
    Generate plots evaluating monitoring interval sensitivity.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generated_files: List[str] = []

    mon_df = df[df["experiment_type"] == "monitoring_interval"] if "experiment_type" in df.columns else pd.DataFrame()

    if mon_df.empty or "monitor_interval" not in mon_df.columns:
        return generated_files

    # 10. Monitoring Interval vs Overhead
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_ov = mon_df.groupby("monitor_interval")["overhead_percentage"].mean()
    grouped_ov.plot(ax=ax, marker="o", color="crimson", linewidth=2.0)
    ax.set_title("10. Monitoring Interval vs Overhead Percentage")
    ax.set_xlabel("Monitoring Interval (ms)")
    ax.set_ylabel("Overhead (%)")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f10 = out_path / "10_monitoring_interval_vs_overhead.png"
    plt.savefig(f10, dpi=300)
    plt.close()
    generated_files.append(str(f10))

    # 11. Monitoring Interval vs LO Utility
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_ut = mon_df.groupby("monitor_interval")["LO_utility_ratio"].mean()
    grouped_ut.plot(ax=ax, marker="s", color="teal", linewidth=2.0)
    ax.set_title("11. Monitoring Interval vs LO Utility Preservation Ratio")
    ax.set_xlabel("Monitoring Interval (ms)")
    ax.set_ylabel("LO Utility Preservation Ratio")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f11 = out_path / "11_monitoring_interval_vs_lo_utility.png"
    plt.savefig(f11, dpi=300)
    plt.close()
    generated_files.append(str(f11))

    return generated_files
