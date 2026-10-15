"""
Reproducible Research Experiment Framework for Mixed-Criticality Real-Time Scheduling.

Provides an experimental evaluation pipeline across standard baselines and AdaptiveGuard:
- EDF
- EDF-VD
- Classical Reactive MC
- EDF-VD + Degraded LO Service
- Flexible MC
- AdaptiveGuard

Strict Reproducibility Guarantees:
Every scheduler evaluated on a given taskset receives the exact same:
1. Task set parameters (generated via UUniFast)
2. Release times and arrival sequences
3. Execution requirements per job
4. Random seed
5. Simulation duration (5000 ms default) and warm-up window (500 ms default)

Results Handling:
- Results are saved to a unique timestamped directory: results/experiments_YYYYMMDD_HHMMSS/
- Raw results are saved as CSV without overwriting previous runs.
- Summary tables are generated aggregating primary and secondary metrics.
"""

import sys
import os
import json
import csv
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.default_config import SimulationConfig
from workloads.generator import TasksetGenerator
from simulator.simulation import Simulation
from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler

# Exact experimental parameter domains defined by research specification
DEFAULT_TASK_COUNTS = [5, 10, 20, 30, 50]
DEFAULT_TARGET_UTILIZATIONS = [0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30, 1.40, 1.50]
DEFAULT_HI_RATIOS = [0.20, 0.40, 0.60]  # 20/80, 40/60, 60/40

RESEARCH_METRICS_FIELDNAMES = [
    "experiment_id",
    "timestamp",
    "scheduler",
    "num_tasks",
    "target_utilization",
    "hi_ratio",
    "seed",
    "duration",
    "warmup_time",
    "U_LO",
    "U_HI_LO",
    "U_HI_HI",
    "U_total_LO",
    "U_total_HI",
    "hi_miss_ratio",             # 1. HI deadline miss ratio (Primary)
    "lo_completion_ratio",      # 2. LO completion ratio
    "lo_utility_ratio",         # 3. LO utility preservation ratio (Primary)
    "average_response_time",    # 4. Average response time
    "worst_response_time",      # 5. Worst response time
    "cpu_utilization",          # 6. CPU utilization
    "mode_switches",            # 7. Mode switches
    "warning_duration",         # 8. Warning duration
    "hi_duration",              # 9. HI duration
    "recovery_duration",        # 10. Recovery duration
    "recovery_time",            # 11. Recovery time
    "total_overhead",           # 12. Total overhead (ms)
    "overhead_percentage",      # 13. Overhead percentage (%)
    "hi_released_count",
    "hi_missed_count",
    "lo_released_count",
    "lo_completed_count",
    "LO_utility",
    "maximum_possible_LO_utility",
]


@dataclass
class ResearchExperimentConfig:
    """Configuration parameters for research experiments."""
    task_counts: List[int] = None
    target_utilizations: List[float] = None
    hi_ratios: List[float] = None
    duration: float = 5000.0
    warmup_time: float = 500.0
    c_hi_factor: float = 2.5
    num_tasksets: int = 10
    seed_base: int = 42
    scenario: str = "BOTH_OVERRUN"
    enable_overhead: bool = True
    output_base_dir: str = "results"

    def __post_init__(self):
        if self.task_counts is None:
            self.task_counts = list(DEFAULT_TASK_COUNTS)
        if self.target_utilizations is None:
            self.target_utilizations = list(DEFAULT_TARGET_UTILIZATIONS)
        if self.hi_ratios is None:
            self.hi_ratios = list(DEFAULT_HI_RATIOS)


def create_timestamped_directory(base_dir: str = "results") -> Path:
    """Create a unique timestamped results directory to prevent overwriting prior runs."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path(base_dir) / f"experiments_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def create_schedulers_for_taskset(taskset: list) -> List[Any]:
    """Instantiate the 6 standard schedulers for a generated taskset."""
    return [
        EDFScheduler(),
        EDFVDScheduler(tasks=taskset),
        ClassicalReactiveMCScheduler(),
        EDFVDDegradedScheduler(tasks=taskset, degraded_service_level=0.50),
        FlexibleMCScheduler(tasks=taskset),
        AdaptiveGuardScheduler(tasks=taskset),
    ]


def run_experiment_on_taskset(
    taskset: list,
    schedulers: list,
    duration: float,
    warmup_time: float,
    seed: int,
    scenario: str = "BOTH_OVERRUN",
    enable_overhead: bool = True,
) -> List[Dict[str, Any]]:
    """
    Execute all schedulers on the exact same taskset under identical conditions.
    """
    results: List[Dict[str, Any]] = []

    for scheduler in schedulers:
        sim_config = SimulationConfig(
            duration=duration,
            warmup_time=warmup_time,
            verbose=False,
            enable_overhead=enable_overhead,
            scheduler_overhead=0.01,
            risk_estimation_overhead=0.005,
            mode_transition_overhead=0.01,
        )
        # Enable proactive risk monitoring only for AdaptiveGuard
        is_adaptive = scheduler.name == "AdaptiveGuard"
        sim = Simulation(
            tasks=taskset,
            config=sim_config,
            scheduler=scheduler,
            scenario=scenario,
            seed=seed,
            enable_monitoring=is_adaptive,
        )
        res = sim.run()
        results.append(res)

    return results


def save_raw_results(results: List[Dict[str, Any]], csv_path: Path) -> None:
    """Write raw experimental results into CSV."""
    with open(csv_path, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RESEARCH_METRICS_FIELDNAMES)
        writer.writeheader()
        for r in results:
            row = {field: r.get(field, "") for field in RESEARCH_METRICS_FIELDNAMES}
            writer.writerow(row)


def generate_summary_tables(raw_results: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """Compute aggregate metric summaries grouped by scheduler and by utilization."""
    from collections import defaultdict

    sched_groups = defaultdict(list)
    util_groups = defaultdict(list)

    for r in raw_results:
        sched_groups[r["scheduler"]].append(r)
        util_groups[(r["target_utilization"], r["scheduler"])].append(r)

    def mean(lst):
        return sum(lst) / len(lst) if lst else 0.0

    # Summary by scheduler
    sched_summary = []
    for s_name, rows in sorted(sched_groups.items()):
        sched_summary.append({
            "scheduler": s_name,
            "runs_count": len(rows),
            "hi_miss_ratio": mean([r["hi_miss_ratio"] for r in rows]),
            "lo_completion_ratio": mean([r["lo_completion_ratio"] for r in rows]),
            "lo_utility_ratio": mean([r["lo_utility_ratio"] for r in rows]),
            "average_response_time": mean([r["average_response_time"] for r in rows]),
            "worst_response_time": max([r["worst_response_time"] for r in rows]) if rows else 0.0,
            "cpu_utilization": mean([r["cpu_utilization"] for r in rows]),
            "mode_switches": mean([r["mode_switches"] for r in rows]),
            "warning_duration": mean([r["warning_duration"] for r in rows]),
            "hi_duration": mean([r["hi_duration"] for r in rows]),
            "recovery_duration": mean([r["recovery_duration"] for r in rows]),
            "recovery_time": mean([r["recovery_time"] for r in rows]),
            "total_overhead": mean([r["total_overhead"] for r in rows]),
            "overhead_percentage": mean([r["overhead_percentage"] for r in rows]),
        })

    # Summary by utilization
    util_summary = []
    for (u_target, s_name), rows in sorted(util_groups.items()):
        util_summary.append({
            "target_utilization": u_target,
            "scheduler": s_name,
            "runs_count": len(rows),
            "hi_miss_ratio": mean([r["hi_miss_ratio"] for r in rows]),
            "lo_utility_ratio": mean([r["lo_utility_ratio"] for r in rows]),
            "lo_completion_ratio": mean([r["lo_completion_ratio"] for r in rows]),
            "mode_switches": mean([r["mode_switches"] for r in rows]),
            "overhead_percentage": mean([r["overhead_percentage"] for r in rows]),
        })

    return {
        "by_scheduler": sched_summary,
        "by_utilization": util_summary,
    }


def run_research_experiments(
    config: Optional[ResearchExperimentConfig] = None,
    output_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run full or sampled research experiments across the parameter grid.
    Saves timestamped outputs and returns metadata and summary data.
    """
    cfg = config or ResearchExperimentConfig()
    out_dir = output_dir or create_timestamped_directory(cfg.output_base_dir)

    generator = TasksetGenerator(c_hi_factor=cfg.c_hi_factor)
    raw_results: List[Dict[str, Any]] = []

    total_tasksets = len(cfg.task_counts) * len(cfg.target_utilizations) * len(cfg.hi_ratios) * cfg.num_tasksets
    print(f"\n=========================================================================================")
    print(f"Starting Research Experiments: {total_tasksets} tasksets | Output: {out_dir}")
    print(f"Task Counts: {cfg.task_counts}")
    print(f"Target Utilizations: {cfg.target_utilizations}")
    print(f"HI/LO Ratios: {cfg.hi_ratios}")
    print(f"Duration: {cfg.duration}ms | Warm-up: {cfg.warmup_time}ms | Repetitions: {cfg.num_tasksets}")
    print(f"=========================================================================================\n")

    exp_counter = 0

    for n_tasks in cfg.task_counts:
        for u_target in cfg.target_utilizations:
            for hi_r in cfg.hi_ratios:
                for ts_idx in range(cfg.num_tasksets):
                    exp_counter += 1
                    seed = cfg.seed_base + (n_tasks * 100000) + int(u_target * 1000) + int(hi_r * 100) + ts_idx

                    # Generate task set ONCE for this parameter configuration
                    taskset = generator.generate_taskset(
                        num_tasks=n_tasks,
                        target_utilization=u_target,
                        hi_ratio=hi_r,
                        seed=seed,
                    )
                    ts_metrics = TasksetGenerator.calculate_taskset_metrics(taskset)
                    schedulers = create_schedulers_for_taskset(taskset)

                    sim_results = run_experiment_on_taskset(
                        taskset=taskset,
                        schedulers=schedulers,
                        duration=cfg.duration,
                        warmup_time=cfg.warmup_time,
                        seed=seed,
                        scenario=cfg.scenario,
                        enable_overhead=cfg.enable_overhead,
                    )

                    for s_res in sim_results:
                        row = {
                            "experiment_id": f"EXP_{exp_counter:06d}",
                            "timestamp": datetime.now().isoformat(),
                            "scheduler": s_res["scheduler"],
                            "num_tasks": n_tasks,
                            "target_utilization": u_target,
                            "hi_ratio": hi_r,
                            "seed": seed,
                            "duration": cfg.duration,
                            "warmup_time": cfg.warmup_time,
                            "U_LO": ts_metrics.U_LO,
                            "U_HI_LO": ts_metrics.U_HI_LO,
                            "U_HI_HI": ts_metrics.U_HI_HI,
                            "U_total_LO": ts_metrics.U_total_LO,
                            "U_total_HI": ts_metrics.U_total_HI,
                            "hi_miss_ratio": s_res["hi_miss_ratio"],
                            "lo_completion_ratio": s_res["lo_completion_ratio"],
                            "lo_utility_ratio": s_res["LO_utility_ratio"],
                            "average_response_time": s_res["average_response_time"],
                            "worst_response_time": s_res["worst_response_time"],
                            "cpu_utilization": s_res["cpu_utilization"],
                            "mode_switches": s_res["mode_switches_count"],
                            "warning_duration": s_res["warning_duration"],
                            "hi_duration": s_res["hi_duration"],
                            "recovery_duration": s_res["recovery_duration"],
                            "recovery_time": s_res["recovery_time"],
                            "total_overhead": s_res["total_overhead_time"],
                            "overhead_percentage": s_res["overhead_percentage"],
                            "hi_released_count": s_res["hi_released_jobs_count"],
                            "hi_missed_count": s_res["hi_missed_jobs_count"],
                            "lo_released_count": s_res["lo_released_jobs_count"],
                            "lo_completed_count": s_res["lo_completed_jobs_count"],
                            "LO_utility": s_res["LO_utility"],
                            "maximum_possible_LO_utility": s_res["maximum_possible_LO_utility"],
                        }
                        raw_results.append(row)

                    if exp_counter % max(1, (total_tasksets // 10)) == 0 or exp_counter == total_tasksets:
                        print(f"Progress: [{exp_counter}/{total_tasksets} tasksets completed] ({len(raw_results)} total simulation runs)")

    # Save outputs to timestamped directory
    raw_csv_path = out_dir / "raw_results.csv"
    save_raw_results(raw_results, raw_csv_path)

    # Save metadata JSON
    meta_path = out_dir / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        meta = {
            "timestamp": datetime.now().isoformat(),
            "config": asdict(cfg),
            "total_tasksets": total_tasksets,
            "total_simulations": len(raw_results),
            "files": {
                "raw_results_csv": str(raw_csv_path.name),
                "summary_by_scheduler_csv": "summary_by_scheduler.csv",
                "summary_by_utilization_csv": "summary_by_utilization.csv",
            }
        }
        json.dump(meta, f, indent=2)

    # Summaries
    summaries = generate_summary_tables(raw_results)

    # Save summary CSVs
    sched_csv_path = out_dir / "summary_by_scheduler.csv"
    if summaries["by_scheduler"]:
        with open(sched_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(summaries["by_scheduler"][0].keys()))
            writer.writeheader()
            writer.writerows(summaries["by_scheduler"])

    util_csv_path = out_dir / "summary_by_utilization.csv"
    if summaries["by_utilization"]:
        with open(util_csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(summaries["by_utilization"][0].keys()))
            writer.writeheader()
            writer.writerows(summaries["by_utilization"])

    print(f"\nAll results saved to: {out_dir}")
    return {
        "output_dir": str(out_dir),
        "raw_results_count": len(raw_results),
        "summaries": summaries,
    }


def print_comparison_table(summaries: Dict[str, Any]) -> None:
    """Print clean comparative summary tables covering all 13 metrics."""
    sched_summary = summaries.get("by_scheduler", [])
    if not sched_summary:
        return

    print("\n" + "=" * 125)
    print(" " * 40 + "RESEARCH EXPERIMENT SUMMARY: PRIMARY METRICS")
    print("=" * 125)
    print(
        f"{'Scheduler':<30} | {'HI Miss Ratio*':<14} | {'LO Util Ratio*':<14} | "
        f"{'LO Comp Ratio':<14} | {'Avg Resp (ms)':<14} | {'Worst Resp(ms)':<14} | {'CPU Util':<8}"
    )
    print("-" * 125)
    for r in sched_summary:
        print(
            f"{r['scheduler']:<30} | {r['hi_miss_ratio']:<14.4f} | {r['lo_utility_ratio']:<14.4f} | "
            f"{r['lo_completion_ratio']:<14.4f} | {r['average_response_time']:<14.2f} | "
            f"{r['worst_response_time']:<14.2f} | {r['cpu_utilization']:<8.3f}"
        )
    print("=" * 125)
    print("  * Primary research metrics: HI deadline miss ratio & LO utility preservation ratio\n")

    print("=" * 135)
    print(" " * 42 + "RESEARCH EXPERIMENT SUMMARY: DYNAMICS & OVERHEAD")
    print("=" * 135)
    print(
        f"{'Scheduler':<30} | {'Switches':<10} | {'Warn Dur(ms)':<13} | {'HI Dur(ms)':<13} | "
        f"{'Rec Dur(ms)':<13} | {'Rec Time(ms)':<13} | {'Overhead(ms)':<13} | {'Overhead(%)':<12}"
    )
    print("-" * 135)
    for r in sched_summary:
        print(
            f"{r['scheduler']:<30} | {r['mode_switches']:<10.2f} | {r['warning_duration']:<13.2f} | "
            f"{r['hi_duration']:<13.2f} | {r['recovery_duration']:<13.2f} | {r['recovery_time']:<13.2f} | "
            f"{r['total_overhead']:<13.4f} | {r['overhead_percentage']:<11.4f}%"
        )
    print("=" * 135 + "\n")


def run_initial_validation_experiment(num_tasksets: int = 10) -> Dict[str, Any]:
    """
    Run the initial 10-task-set validation experiment across representative conditions.
    """
    print(f"--- Running Initial Validation Experiment ({num_tasksets} Task Sets) ---")
    cfg = ResearchExperimentConfig(
        task_counts=[10],
        target_utilizations=[0.80],
        hi_ratios=[0.40],
        duration=5000.0,
        warmup_time=500.0,
        num_tasksets=num_tasksets,
        scenario="BOTH_OVERRUN",
        enable_overhead=True,
    )
    res = run_research_experiments(cfg)
    print_comparison_table(res["summaries"])
    return res


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AdaptiveGuard Research Experiment Framework")
    parser.add_argument("--num-tasksets", type=int, default=10, help="Number of task sets per configuration (10, 100, 1000)")
    parser.add_argument("--full-grid", action="store_true", help="Run full parameter grid across all 5 task counts, 12 utilizations, and 3 HI ratios")
    parser.add_argument("--duration", type=float, default=5000.0, help="Simulation duration in ms")
    parser.add_argument("--warmup", type=float, default=500.0, help="Warm-up duration in ms")

    args = parser.parse_args()

    if args.full_grid:
        cfg = ResearchExperimentConfig(
            duration=args.duration,
            warmup_time=args.warmup,
            num_tasksets=args.num_tasksets,
        )
        res = run_research_experiments(cfg)
        print_comparison_table(res["summaries"])
    else:
        # Default: Execute the initial 10-task-set experiment first as requested
        run_initial_validation_experiment(num_tasksets=args.num_tasksets)

