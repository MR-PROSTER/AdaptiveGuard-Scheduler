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
from schedulers.edf_vd import EDFVDScheduler, calculate_x
from simulator.simulation import Simulation


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(f" Fixed Workload Benchmark: {WORKLOAD_NAME}")
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

    # Calculate and display x factor for EDF-VD
    x_factor = calculate_x(taskset)
    print(f"EDF-VD Deadline Scaling Factor x = {x_factor:.6f} (5/11)\n")

    config = SimulationConfig(duration=100.0, cpu_speed=1.0, verbose=False)

    # ------------------------------------------------------------------
    # 1. NORMAL SCENARIO SIMULATION
    # ------------------------------------------------------------------
    sim_edf_normal = Simulation(tasks=taskset, config=config, scheduler=EDFScheduler(), scenario=ExecutionScenario.NORMAL)
    res_edf_normal = sim_edf_normal.run()

    sim_edf_vd_normal = Simulation(tasks=taskset, config=config, scheduler=EDFVDScheduler(tasks=taskset), scenario=ExecutionScenario.NORMAL)
    res_edf_vd_normal = sim_edf_vd_normal.run()

    # ------------------------------------------------------------------
    # 2. BOTH_OVERRUN SCENARIO SIMULATION
    # ------------------------------------------------------------------
    sim_edf_overrun = Simulation(tasks=taskset, config=config, scheduler=EDFScheduler(), scenario=ExecutionScenario.BOTH_OVERRUN)
    res_edf_overrun = sim_edf_overrun.run()

    sim_edf_vd_overrun = Simulation(tasks=taskset, config=config, scheduler=EDFVDScheduler(tasks=taskset), scenario=ExecutionScenario.BOTH_OVERRUN)
    res_edf_vd_overrun = sim_edf_vd_overrun.run()

    # ------------------------------------------------------------------
    # SIDE-BY-SIDE METRIC COMPARISON (NORMAL)
    # ------------------------------------------------------------------
    print("=" * 82)
    print(" SIDE-BY-SIDE SCHEDULER METRIC COMPARISON (NORMAL SCENARIO)")
    print("=" * 82)
    print(f"{'Metric':<30} │ {'EDF':<22} │ {'EDF-VD':<22}")
    print("─" * 30 + "┼" + "─" * 24 + "┼" + "─" * 24)
    print(f"{'Scheduler Name':<30} │ {res_edf_normal['scheduler']:<22} │ {res_edf_vd_normal['scheduler']:<22}")
    print(f"{'Total Jobs Released':<30} │ {res_edf_normal['total_jobs_released']:<22} │ {res_edf_vd_normal['total_jobs_released']:<22}")
    print(f"{'Completed Jobs Count':<30} │ {res_edf_normal['completed_jobs_count']:<22} │ {res_edf_vd_normal['completed_jobs_count']:<22}")
    print(f"{'Missed Deadline Count':<30} │ {res_edf_normal['missed_jobs_count']:<22} │ {res_edf_vd_normal['missed_jobs_count']:<22}")
    print(f"{'Average Response Time':<30} │ {res_edf_normal['average_response_time']:<19.2f} ms │ {res_edf_vd_normal['average_response_time']:<19.2f} ms")
    print(f"{'CPU Utilization Rate':<30} │ {res_edf_normal['cpu_utilization']*100:<19.2f} % │ {res_edf_vd_normal['cpu_utilization']*100:<19.2f} %")
    print("=" * 82)
    print()

    # ------------------------------------------------------------------
    # SIDE-BY-SIDE METRIC COMPARISON (BOTH_OVERRUN)
    # ------------------------------------------------------------------
    print("=" * 82)
    print(" SIDE-BY-SIDE SCHEDULER METRIC COMPARISON (BOTH_OVERRUN SCENARIO)")
    print("=" * 82)
    print(f"{'Metric':<30} │ {'EDF':<22} │ {'EDF-VD':<22}")
    print("─" * 30 + "┼" + "─" * 24 + "┼" + "─" * 24)
    print(f"{'Scheduler Name':<30} │ {res_edf_overrun['scheduler']:<22} │ {res_edf_vd_overrun['scheduler']:<22}")
    print(f"{'Total Jobs Released':<30} │ {res_edf_overrun['total_jobs_released']:<22} │ {res_edf_vd_overrun['total_jobs_released']:<22}")
    print(f"{'Completed Jobs Count':<30} │ {res_edf_overrun['completed_jobs_count']:<22} │ {res_edf_vd_overrun['completed_jobs_count']:<22}")
    print(f"{'Missed Deadline Count':<30} │ {res_edf_overrun['missed_jobs_count']:<22} │ {res_edf_vd_overrun['missed_jobs_count']:<22}")
    print(f"{'Average Response Time':<30} │ {res_edf_overrun['average_response_time']:<19.2f} ms │ {res_edf_vd_overrun['average_response_time']:<19.2f} ms")
    print(f"{'CPU Utilization Rate':<30} │ {res_edf_overrun['cpu_utilization']*100:<19.2f} % │ {res_edf_vd_overrun['cpu_utilization']*100:<19.2f} %")
    print("=" * 82)


if __name__ == "__main__":
    main()
