"""
Ablation Study Experiment Runner.
"""

from pathlib import Path
from typing import List, Dict, Any

from config.default_config import SimulationConfig
from workloads.generator import TasksetGenerator
from simulator.simulation import Simulation

from schedulers.edf_vd import EDFVDScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.proactive_risk_mc import ProactiveRiskMCScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from experiments.common import save_results_to_csv


def run_ablation_experiment(
    num_tasksets: int = 20,
    duration: float = 5000.0,
    output_csv: str = "results/raw/simulation_results.csv",
    mode: str = "a",
) -> List[Dict[str, Any]]:
    """
    Run ablation study across components A through F.
    """
    generator = TasksetGenerator()
    utilizations = [0.60, 0.80, 1.00, 1.20]
    task_counts = [10, 20]

    ablation_configs = [
        ("A", "EDF-VD", EDFVDScheduler, False, False),
        ("B", "EDF-VD + degraded LO service", EDFVDDegradedScheduler, False, False),
        ("C", "EDF-VD + proactive risk", ProactiveRiskMCScheduler, True, False),
        ("D", "EDF-VD + utility-aware degradation", EDFVDDegradedScheduler, False, True),
        ("E", "EDF-VD + proactive risk + degradation", AdaptiveGuardScheduler, True, False),
        ("F", "Full AdaptiveGuard", AdaptiveGuardScheduler, True, True),
    ]

    results: List[Dict[str, Any]] = []

    print(f"--- Running Ablation Study ({num_tasksets} tasksets per config, duration={duration}ms) ---")

    for u_target in utilizations:
        for n_tasks in task_counts:
            for ts_idx in range(num_tasksets):
                seed = 200000 * ts_idx + int(u_target * 100) + n_tasks
                taskset = generator.generate_taskset(
                    num_tasks=n_tasks,
                    target_utilization=u_target,
                    hi_ratio=0.40,
                    seed=seed,
                )
                metrics = TasksetGenerator.calculate_taskset_metrics(taskset)

                for code, label, sched_cls, enable_monitoring, enable_util_deg in ablation_configs:
                    sched = sched_cls(tasks=taskset)

                    config = SimulationConfig(duration=duration, verbose=False, enable_overhead=True)
                    sim = Simulation(
                        tasks=taskset,
                        config=config,
                        scheduler=sched,
                        scenario="BOTH_OVERRUN",
                        enable_monitoring=enable_monitoring,
                    )
                    if enable_monitoring:
                        sim.mode_controller.warning_enter = 0.50

                    summary = sim.run()

                    row = {
                        "experiment_type": "ablation",
                        "ablation_code": code,
                        "scheduler": f"Ablation-{code}: {label}",
                        "num_tasks": n_tasks,
                        "target_utilization": u_target,
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
    print(f"Ablation study completed. Recorded {len(results)} simulation runs.")
    return results
