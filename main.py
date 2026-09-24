import sys
from pathlib import Path

# Ensure AdaptiveGuard-Scheduler directory is in Python path when executed directly
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.default_config import SimulationConfig
from workloads.fixed_workload import (
    get_fixed_workload,
    WORKLOAD_NAME,
    print_workload_utilization,
    ExecutionScenario,
)
from schedulers.edf import EDFScheduler
from simulator.simulation import Simulation
from controllers.mode_controller import AdaptiveGuardModeController, SystemMode


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(" Utility-Aware LO Degradation & Gradual Recovery Evaluation")
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
    from controllers.degradation_controller import rank_lo_tasks_by_utility_density, calculate_utility_density
    ranked_lo = rank_lo_tasks_by_utility_density(taskset)
    print("LO Tasks Ranked by Utility Density (Higher Priority First):")
    print("-" * 60)
    for idx, t in enumerate(ranked_lo, 1):
        density = calculate_utility_density(t)
        print(f"  Rank {idx}: Task {t.name:<16} | Utility={t.utility:5.1f} | C_LO={t.C_LO:3.1f}ms | Density={density:7.4f}")
    print("-" * 60)
    print()

    # Configure simulation for BOTH_OVERRUN scenario to trigger mode transitions and degradation
    config = SimulationConfig(duration=40.0, cpu_speed=1.0, verbose=False)
    edf_scheduler = EDFScheduler()

    simulation = Simulation(
        tasks=taskset,
        config=config,
        scheduler=edf_scheduler,
        scenario=ExecutionScenario.BOTH_OVERRUN,
        monitor_interval=0.5,
        enable_monitoring=True,
    )
    simulation.mode_controller.warning_enter = 0.50

    print("Executing Fixed Workload (BOTH_OVERRUN Scenario) under AdaptiveGuard...")
    summary = simulation.run()
    print("Simulation Completed Successfully!\n")

    # Display Service Level Changes Log
    service_changes = summary["service_change_log"]
    print("=" * 115)
    print(" UTILITY-AWARE LO SERVICE LEVEL CHANGE LOG")
    print("=" * 115)
    print(f"{'time (ms)':<10} │ {'task':<18} │ {'old service':<12} │ {'new service':<12} │ {'utility density':<16} │ reason")
    print("─" * 115)
    for change in service_changes:
        print(
            f"{change.time:<10.2f} │ {change.task_name:<18} │ {change.old_service:<12.2f} │ "
            f"{change.new_service:<12.2f} │ {change.utility_density:<16.4f} │ {change.reason}"
        )
    print("=" * 115)
    print()

    # Display Utility Metrics Summary
    print("=" * 60)
    print(" UTILITY EVALUATION SUMMARY")
    print("=" * 60)
    print(f"  Achieved LO Utility           : {summary['LO_utility']:.2f}")
    print(f"  Maximum Possible LO Utility   : {summary['maximum_possible_LO_utility']:.2f}")
    print(f"  LO Utility Ratio              : {summary['LO_utility_ratio']:.4f} ({summary['LO_utility_ratio']*100:.2f}%)")
    print("=" * 60)
    print()


if __name__ == "__main__":
    main()
