import sys
from pathlib import Path
from typing import List, Dict, Any

# Ensure AdaptiveGuard-Scheduler directory is in Python path when executed directly
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.default_config import SimulationConfig
from workloads.fixed_workload import (
    get_fixed_workload,
    WORKLOAD_NAME,
    ExecutionScenario,
)
from simulator.simulation import Simulation
from controllers.degradation_controller import rank_lo_tasks_by_utility_density, calculate_utility_density

from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler
from schedulers.proactive_risk_mc import ProactiveRiskMCScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler


def get_all_schedulers(taskset: List[Any]) -> List[Any]:
    """Instantiate all 7 target schedulers for evaluation."""
    return [
        EDFScheduler(),
        EDFVDScheduler(tasks=taskset),
        ClassicalReactiveMCScheduler(),
        EDFVDDegradedScheduler(tasks=taskset, degraded_service_level=0.50),
        FlexibleMCScheduler(tasks=taskset),
        ProactiveRiskMCScheduler(tasks=taskset),
        AdaptiveGuardScheduler(tasks=taskset),
    ]


def run_benchmark_matrix(taskset: List[Any], enable_overhead: bool) -> None:
    """Run full benchmark matrix across 7 schedulers and 4 scenarios."""
    scenarios = [
        ExecutionScenario.NORMAL,
        ExecutionScenario.H1_OVERRUN,
        ExecutionScenario.BOTH_OVERRUN,
        ExecutionScenario.RECOVERY,
    ]

    overhead_label = "OVERHEAD ENABLED" if enable_overhead else "IDEALIZED (OVERHEAD-FREE)"
    print("\n" + "#" * 115)
    print(f" BENCHMARK EVALUATION MATRIX — {overhead_label}")
    print("#" * 115)

    for scenario in scenarios:
        schedulers = get_all_schedulers(taskset)
        scenario_results: List[Dict[str, Any]] = []

        for scheduler in schedulers:
            config = SimulationConfig(
                duration=40.0,
                cpu_speed=1.0,
                verbose=False,
                enable_overhead=enable_overhead,
                scheduler_overhead=0.01,
                risk_estimation_overhead=0.005,
                mode_transition_overhead=0.01,
            )

            # Enable monitoring for proactive controllers
            is_proactive = scheduler.name in ("Proactive Risk / Mode Change", "AdaptiveGuard")
            sim = Simulation(
                tasks=taskset,
                config=config,
                scheduler=scheduler,
                scenario=scenario,
                monitor_interval=0.5,
                enable_monitoring=is_proactive or enable_overhead,
            )
            if is_proactive:
                sim.mode_controller.warning_enter = 0.50

            summary = sim.run()
            scenario_results.append(summary)

        print("\n" + "=" * 115)
        print(f" SCENARIO: {scenario.value:<15} | Mode: {overhead_label}")
        print("=" * 115)
        print(
            f"{'Scheduler':<30} │ {'HI Misses':<10} │ {'LO Ratio':<10} │ "
            f"{'LO Utility':<12} │ {'LO Util Ratio':<14} │ {'Mode Switches':<14} │ Overhead (%)"
        )
        print("─" * 115)

        for res in scenario_results:
            print(
                f"{res['scheduler']:<30} │ {res['hi_missed_jobs_count']:<10d} │ "
                f"{res['lo_completion_ratio']:<10.4f} │ {res['LO_utility']:<12.2f} │ "
                f"{res['LO_utility_ratio']:<14.4f} │ {res['mode_switches_count']:<14d} │ "
                f"{res['overhead_percentage']:.4f}%"
            )
        print("=" * 115)


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Complete Mixed-Criticality Simulator Benchmark")
    print(" Comparative Evaluation of 7 Schedulers Across 4 Scenarios")
    print("==================================================================\n")

    # Load taskset
    taskset = get_fixed_workload()

    print(f"Loaded Taskset Configuration ({WORKLOAD_NAME}):")
    print("-" * 80)
    for task in taskset:
        print(
            f"  [Task {task.task_id}] {task.name:<18} | Crit: {task.criticality.value:<2} | "
            f"T={task.period:4.1f}ms | D={task.relative_deadline:4.1f}ms | "
            f"C_LO={task.C_LO:4.1f}ms | C_HI={task.C_HI:4.1f}ms | Utility={task.utility:5.1f}"
        )
    print("-" * 80)
    print()

    # Display dynamic Utility Density rankings
    ranked_lo = rank_lo_tasks_by_utility_density(taskset)
    print("LO Tasks Ranked by Utility Density (Higher Priority First):")
    print("-" * 60)
    for idx, t in enumerate(ranked_lo, 1):
        density = calculate_utility_density(t)
        print(f"  Rank {idx}: Task {t.name:<16} | Utility={t.utility:5.1f} | C_LO={t.C_LO:3.1f}ms | Density={density:7.4f}")
    print("-" * 60)

    # 1. Run Idealized Overhead-Free Evaluation Matrix
    run_benchmark_matrix(taskset, enable_overhead=False)

    # 2. Run Overhead Enabled Evaluation Matrix
    run_benchmark_matrix(taskset, enable_overhead=True)


if __name__ == "__main__":
    main()
