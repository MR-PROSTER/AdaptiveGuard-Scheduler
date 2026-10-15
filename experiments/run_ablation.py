"""
Ablation Study Experiment Framework.

Explicitly isolates and evaluates the contributions of AdaptiveGuard components:
- A: EDF-VD (no degradation, no proactive risk)
- B: EDF-VD + generic degraded LO service (generic degradation, no proactive risk)
- C: EDF-VD + proactive risk (risk detection and mode switching, no utility-aware degradation)
- D: EDF-VD + utility-aware degradation (utility-aware degradation, no proactive risk)
- E: EDF-VD + proactive risk + degradation (risk + utility-aware degradation, no hysteresis, no recovery)
- F: Full AdaptiveGuard (risk + utility-aware degradation + hysteresis + gradual recovery)

A unified AdaptiveGuardScheduler parameterized by AblationConfig is used across all runs,
ensuring component toggles are strictly isolated without code duplication or seed differences.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.default_config import SimulationConfig
from config.ablation_config import AblationConfig, get_ablation_config, ALL_ABLATION_CONFIGS
from workloads.fixed_workload import get_fixed_workload
from workloads.generator import TasksetGenerator
from simulator.simulation import Simulation
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from experiments.common import save_results_to_csv


def print_ablation_component_matrix() -> None:
    """
    Print a formatted table showing which components are enabled/disabled
    for each ablation configuration (A through F).
    """
    print("\n" + "=" * 115)
    print(" " * 38 + "ABLATION COMPONENT MATRIX")
    print("=" * 115)
    headers = [
        "Code",
        "Configuration Name",
        "Risk",
        "Warn Mode",
        "Degrade LO",
        "Utility-Aware",
        "Hysteresis",
        "Recovery",
    ]
    print(
        f"{headers[0]:<5} | {headers[1]:<40} | {headers[2]:<8} | {headers[3]:<10} | "
        f"{headers[4]:<10} | {headers[5]:<13} | {headers[6]:<10} | {headers[7]:<8}"
    )
    print("-" * 115)
    for code in ("A", "B", "C", "D", "E", "F"):
        cfg = get_ablation_config(code)
        def mark(b: bool) -> str:
            return "YES" if b else "no"
        print(
            f"{cfg.code:<5} | {cfg.name:<40} | {mark(cfg.enable_risk):<8} | "
            f"{mark(cfg.enable_proactive_warning):<10} | {mark(cfg.enable_degradation):<10} | "
            f"{mark(cfg.enable_utility_degradation):<13} | {mark(cfg.enable_hysteresis):<10} | "
            f"{mark(cfg.enable_recovery):<8}"
        )
    print("=" * 115 + "\n")


def run_ablation_fixed_workload(
    duration: float = 200.0,
    enable_overhead: bool = True,
    overload_until_seq: int = 3,
) -> Dict[str, Dict[str, Any]]:
    """
    Execute all 6 ablation configurations on the EXACT same fixed benchmark workload.
    Verify component isolation and non-trivial differences between B & D and E & F.
    """
    print(f"--- Running Ablation on Fixed Canonical Workload (duration={duration}ms, overload_seq<=3) ---")
    summaries: Dict[str, Dict[str, Any]] = {}

    for code in ("A", "B", "C", "D", "E", "F"):
        cfg = get_ablation_config(code)
        tasks = get_fixed_workload()
        sched = AdaptiveGuardScheduler(tasks=tasks, ablation_config=cfg)
        sim_cfg = SimulationConfig(duration=duration, verbose=False, enable_overhead=enable_overhead)
        sim = Simulation(
            tasks=tasks,
            config=sim_cfg,
            scheduler=sched,
            scenario="BOTH_OVERRUN",
            overload_until_seq=overload_until_seq,
        )
        res = sim.run()
        summaries[code] = res

    # Verification assertions
    b_res = summaries["B"]
    d_res = summaries["D"]
    assert abs(b_res["LO_utility_ratio"] - d_res["LO_utility_ratio"]) > 1e-4, (
        f"Verification failed: B and D must not be identical! Got LO util {b_res['LO_utility_ratio']} vs {d_res['LO_utility_ratio']}"
    )

    e_res = summaries["E"]
    f_res = summaries["F"]
    assert e_res["mode_switches_count"] != f_res["mode_switches_count"], (
        f"Verification failed: E and F must not be identical! Got mode switches {e_res['mode_switches_count']} vs {f_res['mode_switches_count']}"
    )

    # Print summary table
    print("\n" + "=" * 115)
    print(" " * 35 + "ABLATION EXPERIMENTAL RESULTS (FIXED WORKLOAD)")
    print("=" * 115)
    print(
        f"{'Code':<5} | {'Configuration':<40} | {'HI Miss':<7} | {'LO Comp':<7} | "
        f"{'LO Util':<7} | {'CPU Util':<8} | {'Switches':<8} | {'Overhead':<8}"
    )
    print("-" * 115)
    for code in ("A", "B", "C", "D", "E", "F"):
        cfg = get_ablation_config(code)
        r = summaries[code]
        hi_rel = r.get("hi_released_jobs_count", max(1, r["total_jobs_released"] - r["lo_released_jobs_count"]))
        hi_miss = r["hi_missed_jobs_count"] / max(1, hi_rel)
        lo_comp = r["lo_completion_ratio"]
        lo_util = r["LO_utility_ratio"]
        cpu_u = r["cpu_utilization"]
        switches = r["mode_switches_count"]
        overhead = r["overhead_percentage"]
        print(
            f"{code:<5} | {cfg.name:<40} | {hi_miss:<7.3f} | {lo_comp:<7.3f} | "
            f"{lo_util:<7.3f} | {cpu_u:<8.3f} | {switches:<8} | {overhead:<7.4f}%"
        )
    print("=" * 115 + "\n")
    return summaries


def run_ablation_experiment(
    num_tasksets: int = 10,
    duration: float = 2000.0,
    output_csv: str = "results/raw/simulation_results.csv",
    mode: str = "a",
) -> List[Dict[str, Any]]:
    """
    Run ablation study across components A through F across synthetic tasksets.
    All configurations evaluate the exact same taskset per seed.
    """
    generator = TasksetGenerator()
    utilizations = [0.60, 0.80, 1.00, 1.20]
    task_counts = [10, 20]

    results: List[Dict[str, Any]] = []

    print(f"--- Running Synthetic Ablation Study ({num_tasksets} tasksets per config, duration={duration}ms) ---")

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

                for code in ("A", "B", "C", "D", "E", "F"):
                    cfg = get_ablation_config(code)
                    sched = AdaptiveGuardScheduler(tasks=taskset, ablation_config=cfg)

                    config = SimulationConfig(duration=duration, verbose=False, enable_overhead=True)
                    sim = Simulation(
                        tasks=taskset,
                        config=config,
                        scheduler=sched,
                        scenario="BOTH_OVERRUN",
                        overload_until_seq=3,
                    )
                    summary = sim.run()

                    hi_released = summary.get("hi_released_jobs_count", summary["total_jobs_released"] - summary["lo_released_jobs_count"])
                    hi_miss_ratio = summary.get("hi_miss_ratio", summary["hi_missed_jobs_count"] / max(1, hi_released))

                    row = {
                        "experiment_type": "ablation",
                        "ablation_code": code,
                        "scheduler": f"Ablation-{code}: {cfg.name}",
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
                        "hi_miss_ratio": hi_miss_ratio,
                        "lo_completion_ratio": summary["lo_completion_ratio"],
                        "LO_utility": summary["LO_utility"],
                        "maximum_possible_LO_utility": summary["maximum_possible_LO_utility"],
                        "LO_utility_ratio": summary["LO_utility_ratio"],
                        "cpu_utilization": summary["cpu_utilization"],
                        "mode_switches": summary["mode_switches_count"],
                        "total_overhead": summary["total_overhead"],
                        "overhead_percentage": summary["overhead_percentage"],
                    }
                    results.append(row)

    save_results_to_csv(results, output_csv=output_csv, mode=mode)
    print(f"Synthetic ablation study completed. Recorded {len(results)} simulation runs.")
    return results


if __name__ == "__main__":
    print_ablation_component_matrix()
    run_ablation_fixed_workload()
