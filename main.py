import sys
from pathlib import Path

# Ensure adaptive-mc-scheduler directory is in Python path when executed directly
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.default_config import SimulationConfig
from workloads.fixed_workload import get_fixed_workload, WORKLOAD_NAME, print_workload_utilization
from simulator.simulation import Simulation


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(f" Fixed Workload Benchmark: {WORKLOAD_NAME}")
    print("==================================================================\n")

    # Load configuration and workload
    config = SimulationConfig(duration=100.0, cpu_speed=1.0, verbose=True)
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
    print(f"Simulation Duration: {config.duration} ms\n")

    # Instantiate and execute simulation
    simulation = Simulation(tasks=taskset, config=config)
    print("Starting Discrete-Event Simulation Engine...")
    summary = simulation.run()
    print("Simulation Completed Successfully!\n")

    # Display Execution Summary
    print("Execution Summary:")
    print("==================================================================")
    print(f"  Final Clock Time       : {summary['final_time']:.2f} ms")
    print(f"  Total Jobs Released    : {summary['total_jobs_released']}")
    print(f"  Completed Jobs Count   : {summary['completed_jobs_count']}")
    print(f"  Missed Deadline Count  : {summary['missed_jobs_count']}")
    print(f"  CPU Busy Execution Time: {summary['cpu_busy_time']:.2f} ms")
    print(f"  CPU Utilization Rate   : {summary['cpu_utilization'] * 100:.2f}%")
    print("==================================================================")


if __name__ == "__main__":
    main()
