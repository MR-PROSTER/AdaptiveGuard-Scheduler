import sys
from pathlib import Path

# Ensure AdaptiveGuard-Scheduler directory is in Python path when executed directly
project_root = Path(__file__).resolve().parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from config.default_config import SimulationConfig
from workloads.fixed_workload import get_fixed_workload, WORKLOAD_NAME, print_workload_utilization
from schedulers.edf import EDFScheduler
from simulator.simulation import Simulation


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(f" Fixed Workload Benchmark: {WORKLOAD_NAME}")
    print("==================================================================\n")

    # Load configuration and workload
    config = SimulationConfig(duration=100.0, cpu_speed=1.0, verbose=False)
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

    # Instantiate EDF scheduler and Simulation
    edf_scheduler = EDFScheduler()
    simulation = Simulation(tasks=taskset, config=config, scheduler=edf_scheduler)

    print("Starting Discrete-Event Simulation Engine (EDF Scheduler)...")
    summary = simulation.run()
    print("Simulation Completed Successfully!\n")

    # Display Execution Timeline
    print("Execution Timeline:")
    print("------------------------------------------------------------------")
    print(f"{'time':<10} event")
    print("------------------------------------------------------------------")
    for event_time, event_desc in summary["timeline"]:
        print(f"{event_time:<10.2f} {event_desc}")
    print("------------------------------------------------------------------\n")

    # Display Execution Summary
    print("Execution Summary:")
    print("==================================================================")
    print(f"  scheduler         : {summary['scheduler']}")
    print(f"  total jobs        : {summary['total_jobs_released']}")
    print(f"  completed jobs    : {summary['completed_jobs_count']}")
    print(f"  deadline misses   : {summary['missed_jobs_count']}")
    print(f"  response time     : {summary['average_response_time']:.2f} ms")
    print(f"  CPU utilization   : {summary['cpu_utilization'] * 100:.2f}%")
    print("==================================================================")


if __name__ == "__main__":
    main()
