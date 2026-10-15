"""
Data Generation Pipeline for Research Visualizations.

Executes actual simulations to generate clean, authentic CSV files for visualization:
1. results/data/utilization_sweep.csv: Multi-run performance vs utilization across 6 schedulers
2. results/data/timeline_results.csv: Real-time risk, mode, and service allocation trajectory
3. results/data/ablation_results.csv: Ablation study across configurations A through F
4. results/data/monitoring_interval_results.csv: Sensitivity to monitoring checkpoint frequency
"""

import sys
import os
import csv
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.default_config import SimulationConfig
from config.ablation_config import get_ablation_config
from workloads.generator import TasksetGenerator
from workloads.fixed_workload import get_fixed_workload
from simulator.simulation import Simulation
from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler


def generate_utilization_data(
    output_csv: Path,
    num_tasksets: int = 5,
    duration: float = 2000.0,
    warmup_time: float = 200.0,
) -> None:
    """Run utilization sweep across all 6 comparative schedulers."""
    print("-> Generating utilization sweep data...")
    generator = TasksetGenerator(c_hi_factor=2.5)
    utilizations = [0.40, 0.60, 0.80, 1.00, 1.20, 1.40]
    n_tasks = 10
    hi_ratio = 0.40

    fieldnames = [
        "scheduler", "target_utilization", "num_tasks", "seed",
        "hi_miss_ratio", "lo_utility_ratio", "lo_completion_ratio",
        "cpu_utilization", "average_response_time", "worst_response_time",
        "mode_switches", "recovery_time", "total_overhead", "overhead_percentage"
    ]

    rows: List[Dict[str, Any]] = []

    for u in utilizations:
        for ts_idx in range(num_tasksets):
            seed = 800000 * ts_idx + int(u * 1000) + 42
            taskset = generator.generate_taskset(
                num_tasks=n_tasks,
                target_utilization=u,
                hi_ratio=hi_ratio,
                seed=seed,
            )

            schedulers = [
                EDFScheduler(),
                EDFVDScheduler(tasks=taskset),
                ClassicalReactiveMCScheduler(),
                EDFVDDegradedScheduler(tasks=taskset, degraded_service_level=0.50),
                FlexibleMCScheduler(tasks=taskset),
                AdaptiveGuardScheduler(tasks=taskset),
            ]

            for s in schedulers:
                cfg = SimulationConfig(
                    duration=duration,
                    warmup_time=warmup_time,
                    enable_overhead=True,
                    verbose=False,
                )
                is_adaptive = s.name == "AdaptiveGuard"
                sim = Simulation(
                    tasks=taskset,
                    config=cfg,
                    scheduler=s,
                    scenario="BOTH_OVERRUN",
                    seed=seed,
                    enable_monitoring=is_adaptive,
                )
                res = sim.run()

                rows.append({
                    "scheduler": s.name,
                    "target_utilization": u,
                    "num_tasks": n_tasks,
                    "seed": seed,
                    "hi_miss_ratio": res["hi_miss_ratio"],
                    "lo_utility_ratio": res["LO_utility_ratio"],
                    "lo_completion_ratio": res["lo_completion_ratio"],
                    "cpu_utilization": res["cpu_utilization"],
                    "average_response_time": res["average_response_time"],
                    "worst_response_time": res["worst_response_time"],
                    "mode_switches": res["mode_switches_count"],
                    "recovery_time": res["recovery_time"],
                    "total_overhead": res["total_overhead_time"],
                    "overhead_percentage": res["overhead_percentage"],
                })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"   Saved {len(rows)} rows to {output_csv}")


def generate_timeline_data(output_csv: Path) -> None:
    """Run detailed simulation of AdaptiveGuard recording dynamic state timeline."""
    print("-> Generating AdaptiveGuard dynamic timeline data...")
    tasks = get_fixed_workload()
    sched = AdaptiveGuardScheduler(tasks=tasks)
    cfg = SimulationConfig(duration=200.0, enable_overhead=True, verbose=False)
    sim = Simulation(
        tasks=tasks,
        config=cfg,
        scheduler=sched,
        scenario="BOTH_OVERRUN",
        overload_until_seq=3,
    )
    sim.run()

    fieldnames = [
        "time", "running_job", "risk", "mode", "trigger",
        "r_util", "r_laxity", "r_overrun", "r_deadline",
        "service_L1", "service_L2", "service_L3", "service_L4",
    ]

    rows: List[Dict[str, Any]] = []
    for entry in sim.state_timeline:
        s_map = entry.get("service_levels", {})
        rows.append({
            "time": entry["time"],
            "running_job": entry["running_job"],
            "risk": entry["risk"],
            "mode": entry["mode"],
            "trigger": entry.get("trigger", ""),
            "r_util": entry.get("r_util", 0.0),
            "r_laxity": entry.get("r_laxity", 0.0),
            "r_overrun": entry.get("r_overrun", 0.0),
            "r_deadline": entry.get("r_deadline", 0.0),
            "service_L1": s_map.get("L1", 1.0),
            "service_L2": s_map.get("L2", 1.0),
            "service_L3": s_map.get("L3", 1.0),
            "service_L4": s_map.get("L4", 1.0),
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"   Saved {len(rows)} timeline checkpoints to {output_csv}")


def generate_ablation_data(output_csv: Path) -> None:
    """Run ablation evaluation across configurations A through F on benchmark workload."""
    print("-> Generating ablation study data...")
    fieldnames = [
        "ablation_code", "scheduler", "hi_miss_ratio", "lo_utility_ratio",
        "lo_completion_ratio", "cpu_utilization", "mode_switches",
        "total_overhead", "overhead_percentage"
    ]

    rows: List[Dict[str, Any]] = []
    for code in ("A", "B", "C", "D", "E", "F"):
        cfg_abl = get_ablation_config(code)
        tasks = get_fixed_workload()
        sched = AdaptiveGuardScheduler(tasks=tasks, ablation_config=cfg_abl)
        sim_cfg = SimulationConfig(duration=200.0, enable_overhead=True, verbose=False)
        sim = Simulation(
            tasks=tasks,
            config=sim_cfg,
            scheduler=sched,
            scenario="BOTH_OVERRUN",
            overload_until_seq=3,
        )
        res = sim.run()

        rows.append({
            "ablation_code": code,
            "scheduler": f"{code}: {cfg_abl.name}",
            "hi_miss_ratio": res["hi_miss_ratio"],
            "lo_utility_ratio": res["LO_utility_ratio"],
            "lo_completion_ratio": res["lo_completion_ratio"],
            "cpu_utilization": res["cpu_utilization"],
            "mode_switches": res["mode_switches_count"],
            "total_overhead": res["total_overhead_time"],
            "overhead_percentage": res["overhead_percentage"],
        })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"   Saved {len(rows)} ablation configurations to {output_csv}")


def generate_monitoring_data(output_csv: Path, num_tasksets: int = 5) -> None:
    """Run sensitivity analysis for monitoring intervals."""
    print("-> Generating monitoring interval sensitivity data...")
    generator = TasksetGenerator(c_hi_factor=2.5)
    intervals = [0.1, 0.25, 0.5, 1.0, 2.0, 5.0]

    fieldnames = [
        "monitor_interval", "num_tasks", "seed",
        "overhead_percentage", "total_overhead", "hi_miss_ratio",
        "lo_utility_ratio", "lo_completion_ratio", "mode_switches"
    ]

    rows: List[Dict[str, Any]] = []
    for interval in intervals:
        for ts_idx in range(num_tasksets):
            seed = 700000 * ts_idx + int(interval * 100)
            taskset = generator.generate_taskset(
                num_tasks=10,
                target_utilization=0.90,
                hi_ratio=0.40,
                seed=seed,
            )

            sched = AdaptiveGuardScheduler(tasks=taskset)
            cfg = SimulationConfig(duration=2000.0, warmup_time=200.0, enable_overhead=True, verbose=False)
            sim = Simulation(
                tasks=taskset,
                config=cfg,
                scheduler=sched,
                scenario="BOTH_OVERRUN",
                seed=seed,
                monitor_interval=interval,
                enable_monitoring=True,
            )
            res = sim.run()

            rows.append({
                "monitor_interval": interval,
                "num_tasks": 10,
                "seed": seed,
                "overhead_percentage": res["overhead_percentage"],
                "total_overhead": res["total_overhead_time"],
                "hi_miss_ratio": res["hi_miss_ratio"],
                "lo_utility_ratio": res["LO_utility_ratio"],
                "lo_completion_ratio": res["lo_completion_ratio"],
                "mode_switches": res["mode_switches_count"],
            })

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"   Saved {len(rows)} monitoring sensitivity runs to {output_csv}")


def generate_all_data(data_dir: str = "results/data") -> Dict[str, Path]:
    """Generate all actual experimental datasets needed for visualization."""
    d_path = Path(data_dir)
    d_path.mkdir(parents=True, exist_ok=True)

    paths = {
        "utilization": d_path / "utilization_sweep.csv",
        "timeline": d_path / "timeline_results.csv",
        "ablation": d_path / "ablation_results.csv",
        "monitoring": d_path / "monitoring_interval_results.csv",
    }

    generate_utilization_data(paths["utilization"])
    generate_timeline_data(paths["timeline"])
    generate_ablation_data(paths["ablation"])
    generate_monitoring_data(paths["monitoring"])

    print("\nAll experimental data generated successfully.\n")
    return paths


if __name__ == "__main__":
    generate_all_data()
