"""
AdaptiveGuard Experiment Runner.
"""

from pathlib import Path
from typing import List, Dict, Any

from config.default_config import SimulationConfig
from workloads.generator import TasksetGenerator
from simulator.simulation import Simulation
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from experiments.common import save_results_to_csv


def run_adaptive_experiment(
    num_tasksets: int = 20,
    duration: float = 5000.0,
    output_csv: str = "results/raw/simulation_results.csv",
    c_hi_factor: float = 2.5,
    enable_overhead: bool = True,
    mode: str = "a",
) -> List[Dict[str, Any]]:
    """
    Run AdaptiveGuard scheduler over synthetic workloads and record performance to CSV.
    """
    generator = TasksetGenerator(c_hi_factor=c_hi_factor)

    utilizations = [0.40, 0.60, 0.80, 1.00, 1.20]
    task_counts = [5, 10, 20]
    hi_ratios = [0.20, 0.40, 0.60]

    results: List[Dict[str, Any]] = []

    print(f"--- Running AdaptiveGuard Experiments ({num_tasksets} tasksets per config, duration={duration}ms) ---")

    for u_target in utilizations:
        for n_tasks in task_counts:
            for hi_r in hi_ratios:
                for ts_idx in range(num_tasksets):
                    seed = 100000 * ts_idx + int(u_target * 100) + n_tasks
                    taskset = generator.generate_taskset(
                        num_tasks=n_tasks,
                        target_utilization=u_target,
                        hi_ratio=hi_r,
                        seed=seed,
                    )
                    metrics = TasksetGenerator.calculate_taskset_metrics(taskset)

                    scheduler = AdaptiveGuardScheduler(tasks=taskset)
                    config = SimulationConfig(
                        duration=duration,
                        verbose=False,
                        enable_overhead=enable_overhead,
                        scheduler_overhead=0.01,
                        risk_estimation_overhead=0.005,
                        mode_transition_overhead=0.01,
                    )
                    sim = Simulation(
                        tasks=taskset,
                        config=config,
                        scheduler=scheduler,
                        scenario="BOTH_OVERRUN",
                        monitor_interval=0.5,
                        enable_monitoring=True,
                    )
                    sim.mode_controller.warning_enter = 0.50
                    summary = sim.run()

                    row = {
                        "experiment_type": "adaptive",
                        "scheduler": scheduler.name,
                        "num_tasks": n_tasks,
                        "target_utilization": u_target,
                        "hi_ratio": hi_r,
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
    print(f"AdaptiveGuard experiment completed. Recorded {len(results)} simulation runs.")
    return results
