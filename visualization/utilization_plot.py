"""
Utilization-based Comparison Plots Module.

Generates:
1. HI deadline miss ratio vs utilization
2. LO utility preservation ratio vs utilization
3. LO completion ratio vs utilization
4. Mode switches vs utilization
5. Overhead vs utilization
"""

from pathlib import Path
from typing import List, Dict, Any
import matplotlib.pyplot as plt
import pandas as pd


def generate_utilization_plots(
    df: pd.DataFrame,
    output_dir: str = "results/plots",
) -> List[str]:
    """
    Generate the 5 core utilization-based metric comparison plots.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generated_files: List[str] = []

    if df.empty or "target_utilization" not in df.columns:
        return generated_files

    # 1. HI Deadline Miss Ratio vs Utilization
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped = df.groupby(["scheduler", "target_utilization"])["hi_miss_ratio"].mean().unstack(level=0)
    grouped.plot(ax=ax, marker="o", linewidth=2.0)
    ax.set_title("1. HI Deadline Miss Ratio vs Utilization")
    ax.set_xlabel("Target Utilization U")
    ax.set_ylabel("HI Deadline Miss Ratio")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f1 = out_path / "1_hi_miss_ratio_vs_utilization.png"
    plt.savefig(f1, dpi=300)
    plt.close()
    generated_files.append(str(f1))

    # 2. LO Utility Preservation vs Utilization
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_u = df.groupby(["scheduler", "target_utilization"])["LO_utility_ratio"].mean().unstack(level=0)
    grouped_u.plot(ax=ax, marker="s", linewidth=2.0)
    ax.set_title("2. LO Utility Preservation Ratio vs Utilization")
    ax.set_xlabel("Target Utilization U")
    ax.set_ylabel("LO Utility Preservation Ratio")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f2 = out_path / "2_lo_utility_preservation_vs_utilization.png"
    plt.savefig(f2, dpi=300)
    plt.close()
    generated_files.append(str(f2))

    # 3. LO Completion Ratio vs Utilization
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_c = df.groupby(["scheduler", "target_utilization"])["lo_completion_ratio"].mean().unstack(level=0)
    grouped_c.plot(ax=ax, marker="^", linewidth=2.0)
    ax.set_title("3. LO Completion Ratio vs Utilization")
    ax.set_xlabel("Target Utilization U")
    ax.set_ylabel("LO Completion Ratio")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f3 = out_path / "3_lo_completion_ratio_vs_utilization.png"
    plt.savefig(f3, dpi=300)
    plt.close()
    generated_files.append(str(f3))

    # 4. Mode Switches vs Utilization
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_m = df.groupby(["scheduler", "target_utilization"])["mode_switches"].mean().unstack(level=0)
    grouped_m.plot(ax=ax, marker="d", linewidth=2.0)
    ax.set_title("4. Mode Switches vs Utilization")
    ax.set_xlabel("Target Utilization U")
    ax.set_ylabel("Mode Switch Count")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f4 = out_path / "4_mode_switches_vs_utilization.png"
    plt.savefig(f4, dpi=300)
    plt.close()
    generated_files.append(str(f4))

    # 5. Overhead Percentage vs Utilization
    fig, ax = plt.subplots(figsize=(8, 5))
    grouped_o = df.groupby(["scheduler", "target_utilization"])["overhead_percentage"].mean().unstack(level=0)
    grouped_o.plot(ax=ax, marker="v", linewidth=2.0)
    ax.set_title("5. Overhead Percentage vs Utilization")
    ax.set_xlabel("Target Utilization U")
    ax.set_ylabel("Overhead (%)")
    ax.grid(True, linestyle=":", alpha=0.6)
    plt.tight_layout()
    f5 = out_path / "5_overhead_vs_utilization.png"
    plt.savefig(f5, dpi=300)
    plt.close()
    generated_files.append(str(f5))

    return generated_files
