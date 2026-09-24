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
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler
from simulator.simulation import Simulation


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(f" Baseline Schedulers Evaluation: {WORKLOAD_NAME}")
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

    config = SimulationConfig(duration=100.0, cpu_speed=1.0, verbose=False)

    scenarios = [
        ("NORMAL", ExecutionScenario.NORMAL),
        ("H1_OVERRUN", ExecutionScenario.H1_OVERRUN),
        ("BOTH_OVERRUN", ExecutionScenario.BOTH_OVERRUN),
    ]

    for scenario_name, scenario_enum in scenarios:
        schedulers = [
            ClassicalReactiveMCScheduler(),
            EDFVDDegradedScheduler(tasks=taskset, degraded_service_level=0.50),
            FlexibleMCScheduler(tasks=taskset),
        ]

        results = []
        for sched in schedulers:
            sim = Simulation(tasks=taskset, config=config, scheduler=sched, scenario=scenario_enum)
            res = sim.run()
            results.append(res)

        print("=" * 102)
        print(f" BASELINE SCHEDULERS COMPARISON: {scenario_name} SCENARIO")
        print("=" * 102)
        print(f"{'Metric':<25} │ {'Classical Reactive MC':<23} │ {'EDF-VD + Degraded LO':<23} │ {'Flexible MC':<23}")
        print("─" * 25 + "┼" + "─" * 25 + "┼" + "─" * 25 + "┼" + "─" * 25)

        row_hi_miss = [f"{r['hi_missed_jobs_count']}" for r in results]
        row_lo_ratio = [f"{r['lo_completion_ratio'] * 100:.2f}%" for r in results]
        row_cpu_util = [f"{r['cpu_utilization'] * 100:.2f}%" for r in results]

        print(f"{'HI Deadline Misses':<25} │ {row_hi_miss[0]:<23} │ {row_hi_miss[1]:<23} │ {row_hi_miss[2]:<23}")
        print(f"{'LO Completion Ratio':<25} │ {row_lo_ratio[0]:<23} │ {row_lo_ratio[1]:<23} │ {row_lo_ratio[2]:<23}")
        print(f"{'CPU Utilization':<25} │ {row_cpu_util[0]:<23} │ {row_cpu_util[1]:<23} │ {row_cpu_util[2]:<23}")
        print("=" * 102)
        print()


if __name__ == "__main__":
    main()
