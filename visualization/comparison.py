"""
Comparative Analysis Plots Module.

Generates:
6. Recovery Time Comparison
12. Ablation Study Comparison
"""

from pathlib import Path
from typing import List
import matplotlib.pyplot as plt
import pandas as pd


def generate_ablation_and_recovery_plots(
    df: pd.DataFrame,
    output_dir: str = "results/plots",
) -> List[str]:
    """
    Generate recovery time and ablation study plots.
    """
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    generated_files: List[str] = []

    # 6. Recovery Time Comparison
    if not df.empty and "recovery_time" in df.columns:
        rec_df = df[df["recovery_time"] > 0]
        if not rec_df.empty:
            fig, ax = plt.subplots(figsize=(8, 5))
            grouped_r = rec_df.groupby("scheduler")["recovery_time"].mean()
            grouped_r.plot(kind="bar", ax=ax, color="darkslateblue")
            ax.set_title("6. Mean Recovery Time Comparison")
            ax.set_ylabel("Recovery Time (ms)")
            ax.set_xlabel("Scheduler")
            plt.xticks(rotation=30, ha="right")
            ax.grid(True, linestyle=":", alpha=0.6)
            plt.tight_layout()
            f6 = out_path / "6_recovery_time_comparison.png"
            plt.savefig(f6, dpi=300)
            plt.close()
            generated_files.append(str(f6))

    # 12. Ablation Study Plot
    abl_df = df[df["experiment_type"] == "ablation"] if "experiment_type" in df.columns else pd.DataFrame()
    if not abl_df.empty and "ablation_code" in abl_df.columns:
        fig, ax = plt.subplots(figsize=(9, 5))
        summary = abl_df.groupby("ablation_code")[["hi_miss_ratio", "LO_utility_ratio"]].mean()
        summary.plot(kind="bar", ax=ax, width=0.7)
        ax.set_title("12. Ablation Study: Impact of Components (A through F)")
        ax.set_xlabel("Ablation Component Code")
        ax.set_ylabel("Ratio")
        ax.set_ylim(0, 1.1)
        plt.xticks(rotation=0)
        ax.grid(True, linestyle=":", alpha=0.6)
        ax.legend(["HI Deadline Miss Ratio", "LO Utility Preservation Ratio"])
        plt.tight_layout()
        f12 = out_path / "12_ablation_study.png"
        plt.savefig(f12, dpi=300)
        plt.close()
        generated_files.append(str(f12))

    return generated_files
