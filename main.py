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


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(" Runtime Monitoring & Risk Estimation Evaluation")
    print("==================================================================\n")

    # Load taskset
    taskset = get_fixed_workload()

    print(f"Loaded Taskset Configuration ({WORKLOAD_NAME}):")
    print("-" * 66)
    for task in taskset:
        print(
            f"  [Task {task.task_id}] {task.name:<20} | Crit: {task.criticality.value:<2} | "
            f"T={task.period:4.1f}ms | D={task.relative_deadline:4.1f}ms | "
            f"C_LO={task.C_LO:4.1f}ms | C_HI={task.C_HI:4.1f}ms | Offset={task.release_offset:4.1f}ms"
        )
    print("-" * 66)
    print()
    print_workload_utilization(taskset)
    print()

    # Configure simulation for H1_OVERRUN scenario with 0.5ms monitoring interval
    config = SimulationConfig(duration=40.0, cpu_speed=1.0, verbose=False)
    edf_scheduler = EDFScheduler()

    simulation = Simulation(
        tasks=taskset,
        config=config,
        scheduler=edf_scheduler,
        scenario=ExecutionScenario.H1_OVERRUN,
        monitor_interval=0.5,
        enable_monitoring=True,
    )

    print("Executing H1_OVERRUN Scenario with Runtime Risk Monitoring (0.5ms interval)...")
    summary = simulation.run()
    print("Simulation Completed Successfully!\n")

    # Display Risk History Timeline
    print("=" * 105)
    print(" RUNTIME RISK ESTIMATION TIMELINE (H1_OVERRUN SCENARIO)")
    print("=" * 105)
    print(
        f"{'Time (ms)':<10} │ {'R_util':<10} │ {'R_laxity':<10} │ {'R_overrun':<10} │ {'R_deadline':<10} │ {'R_total':<10} │ Event / Trigger"
    )
    print("─" * 105)

    risk_history = summary["risk_history"]
    for rm in risk_history:
        print(
            f"{rm.timestamp:<10.2f} │ {rm.r_util:<10.4f} │ {rm.r_laxity:<10.4f} │ "
            f"{rm.r_overrun:<10.4f} │ {rm.r_deadline:<10.4f} │ {rm.r_total:<10.4f} │ {rm.event_trigger}"
        )
    print("=" * 105)


if __name__ == "__main__":
    main()
