"""
Final Publication-Quality Visualization System for AdaptiveGuard.

Generates 14 required research plots and a consolidated summary CSV by directly
reading actual experimental CSV outputs. No synthetic or hardcoded data is used.

Plots:
 1. HI deadline miss ratio vs system utilization (lower is better)
 2. LO utility preservation ratio vs system utilization (higher is better)
 3. LO completion ratio vs utilization (higher is better)
 4. CPU utilization vs utilization
 5. Scheduling overhead vs utilization (lower is better)
 6. Mode switches vs utilization (lower is better)
 7. Recovery time vs utilization (lower is better)
 8. AdaptiveGuard risk score over time
 9. AdaptiveGuard mode over time
10. LO service allocation over time
11. Ablation comparison (Configurations A through F)
12. Monitoring interval vs overhead (lower is better)
13. Monitoring interval vs HI deadline miss ratio (lower is better)
14. Monitoring interval vs LO utility ratio (higher is better)

Summary CSV:
 results/figures/summary_metrics.csv
"""

import os
import sys
import math
from pathlib import Path
from typing import Dict, List, Tuple, Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIGURES_DIR = PROJECT_ROOT / "results" / "figures"
DATA_DIR = PROJECT_ROOT / "results" / "data"

# Standard color palette and styling for schedulers
SCHEDULER_PALETTE: Dict[str, Dict[str, Any]] = {
    "AdaptiveGuard": {
        "color": "#1f77b4",
        "marker": "o",
        "linestyle": "-",
        "linewidth": 2.2,
        "label": "AdaptiveGuard",
    },
    "Flexible MC": {
        "color": "#2ca02c",
        "marker": "s",
        "linestyle": "-",
        "linewidth": 1.8,
        "label": "Flexible MC",
    },
    "EDF-VD + Degraded LO Service": {
        "color": "#ff7f0e",
        "marker": "^",
        "linestyle": "--",
        "linewidth": 1.8,
        "label": "EDF-VD + Degraded LO",
    },
    "Classical Reactive MC": {
        "color": "#d62728",
        "marker": "v",
        "linestyle": "-.",
        "linewidth": 1.8,
        "label": "Classical Reactive MC",
    },
    "EDF-VD": {
        "color": "#9467bd",
        "marker": "D",
        "linestyle": ":",
        "linewidth": 1.8,
        "label": "EDF-VD",
    },
    "EDF": {
        "color": "#7f7f7f",
        "marker": "x",
        "linestyle": (0, (3, 1, 1, 1)),
        "linewidth": 1.5,
        "label": "EDF",
    },
}

# Desired display ordering of schedulers
SCHEDULER_ORDER = [
    "AdaptiveGuard",
    "Flexible MC",
    "EDF-VD + Degraded LO Service",
    "Classical Reactive MC",
    "EDF-VD",
    "EDF",
]


def apply_plot_style(ax: plt.Axes, title: str, xlabel: str, ylabel: str) -> None:
    """Apply consistent styling across all scientific figures."""
    ax.set_title(title, fontsize=13, fontweight="bold", pad=12)
    ax.set_xlabel(xlabel, fontsize=11, fontweight="medium", labelpad=8)
    ax.set_ylabel(ylabel, fontsize=11, fontweight="medium", labelpad=8)
    ax.grid(True, linestyle="--", alpha=0.35, color="#888888")
    ax.tick_params(axis="both", which="major", labelsize=10)
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)


def plot_metric_vs_utilization(
    df: pd.DataFrame,
    metric_col: str,
    title: str,
    ylabel: str,
    filename: str,
    quality_label: str = "",
    percent_fmt: bool = True,
) -> None:
    """Helper to generate comparison line plots with error bars across utilizations."""
    fig, ax = plt.subplots(figsize=(8.5, 5.5), dpi=300)
    full_title = f"{title}\n[{quality_label}]" if quality_label else title
    apply_plot_style(ax, full_title, "System Target Utilization", ylabel)

    # Compute mean and standard error for each scheduler and utilization
    for sched in SCHEDULER_ORDER:
        sub = df[df["scheduler"] == sched]
        if sub.empty:
            continue
        grouped = sub.groupby("target_utilization")[metric_col].agg(["mean", "std", "count"]).reset_index()
        grouped["se"] = grouped["std"] / np.sqrt(grouped["count"].replace(0, 1))
        grouped["se"] = grouped["se"].fillna(0.0)

        style = SCHEDULER_PALETTE.get(sched, {"color": "black", "marker": "o", "linestyle": "-"})
        ax.errorbar(
            grouped["target_utilization"],
            grouped["mean"],
            yerr=grouped["se"],
            label=style.get("label", sched),
            color=style.get("color", "black"),
            marker=style.get("marker", "o"),
            linestyle=style.get("linestyle", "-"),
            linewidth=style.get("linewidth", 1.8),
            markersize=6,
            capsize=3,
            capthick=1.2,
            alpha=0.95,
        )

    if percent_fmt:
        ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.xaxis.set_major_locator(ticker.MultipleLocator(0.20))
    ax.legend(loc="best", frameon=True, framealpha=0.9, fontsize=9.5)
    plt.tight_layout()
    out_path = FIGURES_DIR / filename
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_1(df_util: pd.DataFrame) -> None:
    """1. HI deadline miss ratio vs system utilization (lower is better)."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="hi_miss_ratio",
        title="HI Deadline Miss Ratio vs System Utilization",
        ylabel="HI Deadline Miss Ratio (%)",
        filename="01_hi_deadline_miss_ratio_vs_utilization.png",
        quality_label="lower is better",
        percent_fmt=True,
    )


def generate_plot_2(df_util: pd.DataFrame) -> None:
    """2. LO utility preservation ratio vs system utilization (higher is better)."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="lo_utility_ratio",
        title="LO Utility Preservation Ratio vs System Utilization",
        ylabel="LO Utility Preservation Ratio (%)",
        filename="02_lo_utility_preservation_ratio_vs_utilization.png",
        quality_label="higher is better",
        percent_fmt=True,
    )


def generate_plot_3(df_util: pd.DataFrame) -> None:
    """3. LO completion ratio vs utilization (higher is better)."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="lo_completion_ratio",
        title="LO Task Completion Ratio vs System Utilization",
        ylabel="LO Completion Ratio (%)",
        filename="03_lo_completion_ratio_vs_utilization.png",
        quality_label="higher is better",
        percent_fmt=True,
    )


def generate_plot_4(df_util: pd.DataFrame) -> None:
    """4. CPU utilization vs utilization."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="cpu_utilization",
        title="Achieved CPU Utilization vs Target System Utilization",
        ylabel="CPU Utilization (%)",
        filename="04_cpu_utilization_vs_utilization.png",
        quality_label="",
        percent_fmt=True,
    )


def generate_plot_5(df_util: pd.DataFrame) -> None:
    """5. Scheduling overhead vs utilization (lower is better)."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="overhead_percentage",
        title="Computational Overhead vs System Utilization",
        ylabel="Overhead (% of Simulation Duration)",
        filename="05_scheduling_overhead_vs_utilization.png",
        quality_label="lower is better",
        percent_fmt=False,
    )


def generate_plot_6(df_util: pd.DataFrame) -> None:
    """6. Mode switches vs utilization (lower is better)."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="mode_switches",
        title="Mode Switch Frequency vs System Utilization",
        ylabel="Number of Mode Switches",
        filename="06_mode_switches_vs_utilization.png",
        quality_label="lower is better",
        percent_fmt=False,
    )


def generate_plot_7(df_util: pd.DataFrame) -> None:
    """7. Recovery time vs utilization (lower is better)."""
    plot_metric_vs_utilization(
        df_util,
        metric_col="recovery_time",
        title="Total Mode Recovery Time vs System Utilization",
        ylabel="Recovery Time (ms)",
        filename="07_recovery_time_vs_utilization.png",
        quality_label="lower is better",
        percent_fmt=False,
    )


def generate_plot_8(df_timeline: pd.DataFrame) -> None:
    """8. AdaptiveGuard risk score over time."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 6.5), sharex=True, dpi=300,
                                   gridspec_kw={"height_ratios": [2.5, 1.8]})
    
    # Subplot 1: Total risk score with thresholds
    apply_plot_style(ax1, "AdaptiveGuard Dynamic Risk Score Evolution Over Time", "", "Total Risk R(t)")
    ax1.plot(df_timeline["time"], df_timeline["risk"], color="#1f77b4", linewidth=2.0, label="Composite Risk R(t)")
    ax1.axhline(0.35, color="#ff7f0e", linestyle="--", linewidth=1.5, label="Warning Threshold (0.35)")
    ax1.axhline(0.70, color="#d62728", linestyle="--", linewidth=1.5, label="HI Mode Threshold (0.70)")
    
    # Risk zones shading
    ax1.axhspan(0.0, 0.35, color="#2ca02c", alpha=0.08, label="Normal Risk Zone")
    ax1.axhspan(0.35, 0.70, color="#ff7f0e", alpha=0.10, label="Warning Risk Zone")
    ax1.axhspan(0.70, 1.05, color="#d62728", alpha=0.10, label="Critical Risk Zone")
    ax1.set_ylim(-0.02, 1.05)
    ax1.legend(loc="upper right", framealpha=0.9, fontsize=9)

    # Subplot 2: Breakdown of risk components
    apply_plot_style(ax2, "", "Simulation Time (ms)", "Component Risk")
    ax2.plot(df_timeline["time"], df_timeline["r_util"], label="r_util (Utilization)", color="#9467bd", linewidth=1.4)
    ax2.plot(df_timeline["time"], df_timeline["r_laxity"], label="r_laxity (Laxity)", color="#8c564b", linewidth=1.4)
    ax2.plot(df_timeline["time"], df_timeline["r_overrun"], label="r_overrun (Execution)", color="#e377c2", linewidth=1.4)
    ax2.plot(df_timeline["time"], df_timeline["r_deadline"], label="r_deadline (Proximity)", color="#17becf", linewidth=1.4)
    ax2.set_ylim(-0.02, 1.05)
    ax2.legend(loc="upper right", framealpha=0.9, fontsize=8.5, ncol=2)

    plt.tight_layout()
    out_path = FIGURES_DIR / "08_adaptive_guard_risk_score_over_time.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_9(df_timeline: pd.DataFrame) -> None:
    """9. AdaptiveGuard mode over time."""
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    apply_plot_style(ax, "AdaptiveGuard Operational Mode Evolution Over Time", "Simulation Time (ms)", "System Mode")

    mode_map = {"LO": 0, "WARNING": 1, "HI": 2, "RECOVERY": 3}
    mode_nums = [mode_map.get(m, 0) for m in df_timeline["mode"]]

    ax.step(df_timeline["time"], mode_nums, where="post", color="#1f77b4", linewidth=2.2, label="System Mode")
    
    # Fill colors for modes
    ax.set_yticks([0, 1, 2, 3])
    ax.set_yticklabels(["LO Mode", "WARNING Mode", "HI Mode", "RECOVERY Mode"], fontweight="semibold")
    ax.set_ylim(-0.5, 3.5)

    # Highlight intervals
    for mode_name, val, col, alpha in [
        ("LO Mode", 0, "#2ca02c", 0.08),
        ("WARNING Mode", 1, "#ff7f0e", 0.12),
        ("HI Mode", 2, "#d62728", 0.12),
        ("RECOVERY Mode", 3, "#9467bd", 0.12),
    ]:
        ax.axhspan(val - 0.45, val + 0.45, color=col, alpha=alpha)

    plt.tight_layout()
    out_path = FIGURES_DIR / "09_adaptive_guard_mode_over_time.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_10(df_timeline: pd.DataFrame) -> None:
    """10. LO service allocation over time."""
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=300)
    apply_plot_style(ax, "Dynamic LO Service Level Allocation Over Time\n[higher is better]", "Simulation Time (ms)", "Service Level Allocation (θ)")

    service_cols = [c for c in df_timeline.columns if c.startswith("service_")]
    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    for i, col in enumerate(service_cols):
        task_id = col.replace("service_", "")
        c = colors[i % len(colors)]
        ax.step(df_timeline["time"], df_timeline[col], where="post", color=c, linewidth=1.8, label=f"Task {task_id}")

    ax.set_ylim(-0.05, 1.10)
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.legend(loc="lower left", framealpha=0.9, fontsize=9.5)

    plt.tight_layout()
    out_path = FIGURES_DIR / "10_lo_service_allocation_over_time.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_11(df_ablation: pd.DataFrame) -> None:
    """11. Ablation comparison across configurations A through F."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.0), dpi=300)

    configs = df_ablation["ablation_code"].tolist()
    labels = [
        "A: Baseline\n(EDF-VD)",
        "B: Generic\nDegradation",
        "C: Proactive\nRisk",
        "D: Utility\nDegradation",
        "E: Risk +\nDegradation",
        "F: Full\nAdaptiveGuard",
    ]
    x = np.arange(len(configs))
    width = 0.35

    # Subplot 1: HI Miss Ratio (lower is better) & LO Utility Ratio (higher is better)
    apply_plot_style(ax1, "Ablation: Safety & Utility Trade-off", "Configuration", "Ratio (%)")
    rects1 = ax1.bar(x - width/2, df_ablation["hi_miss_ratio"] * 100, width, label="HI Deadline Miss % (lower is better)", color="#d62728", alpha=0.85)
    rects2 = ax1.bar(x + width/2, df_ablation["lo_utility_ratio"] * 100, width, label="LO Utility Ratio % (higher is better)", color="#2ca02c", alpha=0.85)
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels, fontsize=8.5)
    ax1.legend(loc="upper left", fontsize=8.5, framealpha=0.9)
    ax1.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=100.0, decimals=0))

    # Add data labels
    for rect in rects1:
        h = rect.get_height()
        if h > 0:
            ax1.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                         textcoords="offset points", ha="center", va="bottom", fontsize=7.5)
    for rect in rects2:
        h = rect.get_height()
        ax1.annotate(f"{h:.1f}%", xy=(rect.get_x() + rect.get_width()/2, h), xytext=(0, 3),
                     textcoords="offset points", ha="center", va="bottom", fontsize=7.5)

    # Subplot 2: Mode Switches & Overhead
    apply_plot_style(ax2, "Ablation: Stability & Overhead\n[lower is better]", "Configuration", "Count / Overhead")
    ax2.plot(x, df_ablation["mode_switches"], marker="o", color="#1f77b4", linewidth=2.0, label="Mode Switches (lower is better)")
    ax2_twin = ax2.twinx()
    ax2_twin.plot(x, df_ablation["overhead_percentage"], marker="s", color="#ff7f0e", linewidth=2.0, linestyle="--", label="Overhead % (lower is better)")
    ax2_twin.set_ylabel("Overhead (%)", color="#ff7f0e", fontsize=10, fontweight="medium")
    ax2_twin.tick_params(axis="y", labelcolor="#ff7f0e")
    ax2_twin.spines["top"].set_visible(False)

    ax2.set_xticks(x)
    ax2.set_xticklabels(labels, fontsize=8.5)
    lines_1, labels_1 = ax2.get_legend_handles_labels()
    lines_2, labels_2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines_1 + lines_2, labels_1 + labels_2, loc="upper right", fontsize=8.5, framealpha=0.9)

    plt.tight_layout()
    out_path = FIGURES_DIR / "11_ablation_comparison.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_12(df_monitor: pd.DataFrame) -> None:
    """12. Monitoring interval vs overhead (lower is better)."""
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    apply_plot_style(ax, "Monitoring Interval vs Computational Overhead\n[lower is better]",
                     "Monitoring Checkpoint Interval Δt (ms)", "Computational Overhead (%)")

    grouped = df_monitor.groupby("monitor_interval")["overhead_percentage"].agg(["mean", "std", "count"]).reset_index()
    grouped["se"] = grouped["std"] / np.sqrt(grouped["count"].replace(0, 1))

    ax.errorbar(
        grouped["monitor_interval"],
        grouped["mean"],
        yerr=grouped["se"],
        marker="o",
        color="#1f77b4",
        linewidth=2.0,
        markersize=6,
        capsize=4,
        label="Overhead %",
    )
    ax.legend(loc="best", framealpha=0.9, fontsize=9.5)
    plt.tight_layout()
    out_path = FIGURES_DIR / "12_monitoring_interval_vs_overhead.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_13(df_monitor: pd.DataFrame) -> None:
    """13. Monitoring interval vs HI deadline miss ratio (lower is better)."""
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    apply_plot_style(ax, "Monitoring Interval vs HI Deadline Miss Ratio\n[lower is better]",
                     "Monitoring Checkpoint Interval Δt (ms)", "HI Deadline Miss Ratio (%)")

    grouped = df_monitor.groupby("monitor_interval")["hi_miss_ratio"].agg(["mean", "std", "count"]).reset_index()
    grouped["se"] = grouped["std"] / np.sqrt(grouped["count"].replace(0, 1))

    ax.errorbar(
        grouped["monitor_interval"],
        grouped["mean"],
        yerr=grouped["se"],
        marker="s",
        color="#d62728",
        linewidth=2.0,
        markersize=6,
        capsize=4,
        label="HI Miss Ratio",
    )
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.legend(loc="best", framealpha=0.9, fontsize=9.5)
    plt.tight_layout()
    out_path = FIGURES_DIR / "13_monitoring_interval_vs_hi_deadline_miss_ratio.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_plot_14(df_monitor: pd.DataFrame) -> None:
    """14. Monitoring interval vs LO utility ratio (higher is better)."""
    fig, ax = plt.subplots(figsize=(8, 5), dpi=300)
    apply_plot_style(ax, "Monitoring Interval vs LO Utility Preservation Ratio\n[higher is better]",
                     "Monitoring Checkpoint Interval Δt (ms)", "LO Utility Preservation Ratio (%)")

    grouped = df_monitor.groupby("monitor_interval")["lo_utility_ratio"].agg(["mean", "std", "count"]).reset_index()
    grouped["se"] = grouped["std"] / np.sqrt(grouped["count"].replace(0, 1))

    ax.errorbar(
        grouped["monitor_interval"],
        grouped["mean"],
        yerr=grouped["se"],
        marker="^",
        color="#2ca02c",
        linewidth=2.0,
        markersize=6,
        capsize=4,
        label="LO Utility Preservation",
    )
    ax.yaxis.set_major_formatter(ticker.PercentFormatter(xmax=1.0, decimals=0))
    ax.legend(loc="best", framealpha=0.9, fontsize=9.5)
    plt.tight_layout()
    out_path = FIGURES_DIR / "14_monitoring_interval_vs_lo_utility_ratio.png"
    plt.savefig(out_path)
    plt.close()
    print(f"Saved: {out_path.name}")


def generate_summary_csv(df_util: pd.DataFrame) -> Path:
    """Generate consolidated research summary CSV grouping across all schedulers."""
    summary_path = FIGURES_DIR / "summary_metrics.csv"
    summary_df = (
        df_util.groupby("scheduler")
        .agg({
            "hi_miss_ratio": ["mean", "std"],
            "lo_utility_ratio": ["mean", "std"],
            "lo_completion_ratio": ["mean", "std"],
            "cpu_utilization": ["mean", "std"],
            "average_response_time": ["mean", "std"],
            "worst_response_time": ["mean", "std"],
            "mode_switches": ["mean", "std"],
            "recovery_time": ["mean", "std"],
            "total_overhead": ["mean", "std"],
            "overhead_percentage": ["mean", "std"],
        })
        .round(4)
    )
    # Flatten multiindex columns for clarity
    summary_df.columns = [f"{col[0]}_{col[1]}" for col in summary_df.columns]
    summary_df.to_csv(summary_path)
    print(f"Saved consolidated summary CSV: {summary_path}")
    return summary_path


def render_all_plots() -> None:
    """Load authentic CSV experiment results and render all 14 figures + summary CSV."""
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    util_csv = DATA_DIR / "utilization_sweep.csv"
    timeline_csv = DATA_DIR / "timeline_results.csv"
    ablation_csv = DATA_DIR / "ablation_results.csv"
    monitor_csv = DATA_DIR / "monitoring_interval_results.csv"

    for p in [util_csv, timeline_csv, ablation_csv, monitor_csv]:
        if not p.exists():
            raise FileNotFoundError(f"Required experiment data file not found: {p}")

    df_util = pd.read_csv(util_csv)
    df_timeline = pd.read_csv(timeline_csv)
    df_ablation = pd.read_csv(ablation_csv)
    df_monitor = pd.read_csv(monitor_csv)

    print("\n--- Generating Publication-Quality Figures ---")
    generate_plot_1(df_util)
    generate_plot_2(df_util)
    generate_plot_3(df_util)
    generate_plot_4(df_util)
    generate_plot_5(df_util)
    generate_plot_6(df_util)
    generate_plot_7(df_util)
    generate_plot_8(df_timeline)
    generate_plot_9(df_timeline)
    generate_plot_10(df_timeline)
    generate_plot_11(df_ablation)
    generate_plot_12(df_monitor)
    generate_plot_13(df_monitor)
    generate_plot_14(df_monitor)

    generate_summary_csv(df_util)
    print("\n--- All 14 figures and summary CSV generated successfully. ---\n")


if __name__ == "__main__":
    render_all_plots()
