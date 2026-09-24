"""
Sensitivity Experiments Runner.
"""

from pathlib import Path
from typing import List, Dict, Any

from config.default_config import SimulationConfig
from workloads.generator import TasksetGenerator
from simulator.simulation import Simulation
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from experiments.common import save_results_to_csv


def run_sensitivity_experiments(
    num_tasksets: int = 15,
    duration: float = 5000.0,
    output_csv: str = "results/raw/simulation_results.csv",
    mode: str = "a",
) -> List[Dict[str, Any]]:
    """
    Run risk weight sensitivity and threshold sensitivity experiments.
    """
    generator = TasksetGenerator()
    results: List[Dict[str, Any]] = []

    print(f"--- Running Sensitivity Experiments ({num_tasksets} tasksets per config, duration={duration}ms) ---")

    # 1. Risk Weight Sensitivity
    weight_sets = [
        ("Default (30/30/25/15)", 0.30, 0.30, 0.25, 0.15),
        ("Util-Heavy (50/20/15/15)", 0.50, 0.20, 0.15, 0.15),
        ("Laxity-Heavy (20/50/15/15)", 0.20, 0.50, 0.15, 0.15),
        ("Overrun-Heavy (20/20/45/15)", 0.20, 0.20, 0.45, 0.15),
        ("Deadline-Heavy (20/20/15/45)", 0.20, 0.20, 0.15, 0.45),
        ("Equal Weights (25/25/25/25)", 0.25, 0.25, 0.25, 0.25),
    ]

    for label, w_util, w_laxity, w_overrun, w_deadline in weight_sets:
        for ts_idx in range(num_tasksets):
            seed = 300000 * ts_idx + 1
            taskset = generator.generate_taskset(num_tasks=10, target_utilization=1.00, hi_ratio=0.40, seed=seed)
            metrics = TasksetGenerator.calculate_taskset_metrics(taskset)

            scheduler = AdaptiveGuardScheduler(tasks=taskset)
            config = SimulationConfig(duration=duration, verbose=False, enable_overhead=True)
            sim = Simulation(
                tasks=taskset,
                config=config,
                scheduler=scheduler,
                scenario="BOTH_OVERRUN",
                monitor_interval=0.5,
                enable_monitoring=True,
            )
            sim.risk_estimator.w_util = w_util
            sim.risk_estimator.w_laxity = w_laxity
            sim.risk_estimator.w_overrun = w_overrun
            sim.risk_estimator.w_deadline = w_deadline
            sim.mode_controller.warning_enter = 0.50

            summary = sim.run()

            row = {
                "experiment_type": "weight_sensitivity",
                "sensitivity_param": label,
                "scheduler": scheduler.name,
                "num_tasks": 10,
                "target_utilization": 1.00,
                "hi_ratio": 0.40,
                "seed": seed,
                "U_LO": metrics.U_LO,
                "U_HI_LO": metrics.U_HI_LO,
                "U_HI_HI": metrics.U_HI_HI,
                "U_total_LO": metrics.U_total_LO,
                "U_total_HI": metrics.U_total_HI,
                "hi_missed_count": summary["hi_missed_jobs_count"],
                "hi_miss_ratio": summary["hi_missed_jobs_count"] / max(1, summary["total_jobs_released"]),
                "lo_completion_ratio": summary["lo_completion_ratio"],
                "LO_utility": summary["LO_utility"],
                "maximum_possible_LO_utility": summary["maximum_possible_LO_utility"],
                "LO_utility_ratio": summary["LO_utility_ratio"],
                "mode_switches": summary["mode_switches_count"],
                "total_overhead": summary["total_overhead"],
                "overhead_percentage": summary["overhead_percentage"],
            }
            results.append(row)

    # 2. Threshold Sensitivity
    warning_thresholds = [0.50, 0.60, 0.70]
    hi_thresholds = [0.75, 0.80, 0.85]
    recovery_thresholds = [0.30, 0.40, 0.50]

    for w_t in warning_thresholds:
        for h_t in hi_thresholds:
            for r_t in recovery_thresholds:
                param_label = f"W={w_t:.2f}_H={h_t:.2f}_R={r_t:.2f}"
                for ts_idx in range(num_tasksets):
                    seed = 400000 * ts_idx + int(w_t * 100)
                    taskset = generator.generate_taskset(num_tasks=10, target_utilization=1.00, hi_ratio=0.40, seed=seed)
                    metrics = TasksetGenerator.calculate_taskset_metrics(taskset)

                    scheduler = AdaptiveGuardScheduler(tasks=taskset)
                    config = SimulationConfig(duration=duration, verbose=False, enable_overhead=True)
                    sim = Simulation(
                        tasks=taskset,
                        config=config,
                        scheduler=scheduler,
                        scenario="BOTH_OVERRUN",
                        monitor_interval=0.5,
                        enable_monitoring=True,
                    )
                    sim.mode_controller.warning_enter = w_t
                    sim.mode_controller.hi_enter = h_t
                    sim.mode_controller.recovery_enter = r_t

                    summary = sim.run()

                    row = {
                        "experiment_type": "threshold_sensitivity",
                        "sensitivity_param": param_label,
                        "scheduler": scheduler.name,
                        "num_tasks": 10,
                        "target_utilization": 1.00,
                        "hi_ratio": 0.40,
                        "seed": seed,
                        "U_LO": metrics.U_LO,
                        "U_HI_LO": metrics.U_HI_LO,
                        "U_HI_HI": metrics.U_HI_HI,
                        "U_total_LO": metrics.U_total_LO,
                        "U_total_HI": metrics.U_total_HI,
                        "hi_missed_count": summary["hi_missed_jobs_count"],
                        "hi_miss_ratio": summary["hi_missed_jobs_count"] / max(1, summary["total_jobs_released"]),
                        "lo_completion_ratio": summary["lo_completion_ratio"],
                        "LO_utility": summary["LO_utility"],
                        "maximum_possible_LO_utility": summary["maximum_possible_LO_utility"],
                        "LO_utility_ratio": summary["LO_utility_ratio"],
                        "mode_switches": summary["mode_switches_count"],
                        "total_overhead": summary["total_overhead"],
                        "overhead_percentage": summary["overhead_percentage"],
                    }
                    results.append(row)

    save_results_to_csv(results, output_csv=output_csv, mode=mode)
    print(f"Sensitivity experiments completed. Recorded {len(results)} simulation runs.")
    return results
