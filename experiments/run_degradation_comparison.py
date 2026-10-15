import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from config.default_config import SimulationConfig
from simulator.simulation import Simulation
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from simulator.task import Criticality


def run_and_print_scheduler(name: str, utility_aware: bool, degraded_service_level: float = 0.50):
    print("=" * 80)
    print(f"RUNNING: {name}")
    print("=" * 80)

    tasks = get_stress_20ms_workload()
    sched = EDFVDDegradedScheduler(
        tasks=tasks,
        degraded_service_level=degraded_service_level,
        utility_aware=utility_aware,
    )

    config = SimulationConfig(
        duration=40.0,
        verbose=False,
        enable_overhead=True,
        scheduler_overhead=0.01,
        risk_estimation_overhead=0.005,
        mode_transition_overhead=0.01,
    )

    sim = Simulation(
        tasks=tasks,
        config=config,
        scheduler=sched,
        scenario=ExecutionScenario.BOTH_OVERRUN,
        enable_monitoring=False,
    )

    summary = sim.run()

    print("\n--- Summary Metrics ---")
    print(f"Scheduler:            {summary['scheduler']}")
    print(f"HI Miss Ratio:        {summary['hi_miss_ratio']:.4f} ({summary['hi_missed_jobs_count']}/{summary['hi_released_jobs_count']})")
    print(f"LO Completion Ratio:  {summary['lo_completion_ratio']:.4f} ({summary['lo_completed_jobs_count']}/{summary['lo_released_jobs_count']})")
    print(f"LO Utility Achieved:  {summary['LO_utility']:.2f} / {summary['maximum_possible_LO_utility']:.2f}")
    print(f"LO Utility Ratio:     {summary['LO_utility_ratio']:.4f}")
    print(f"CPU Utilization:      {summary['cpu_utilization']:.4f}")
    print(f"Mode Switches:        {summary['mode_switches_count']}")

    print("\n--- Per-Task Service and Utility Records ---")
    reports = sim.degradation_controller.task_service_records
    print(f"{'Task Name':<15} | {'Density':<8} | {'Requested':<10} | {'Allocated':<10} | {'Achieved':<10} | {'Service Frac':<12} | {'Utility':<8} | {'Achieved Util':<12}")
    print("-" * 105)
    for tid, rec in sorted(reports.items(), key=lambda item: item[1].utility_density, reverse=True):
        print(
            f"{rec.task_name:<15} | {rec.utility_density:<8.2f} | {rec.requested_execution:<10.1f} | "
            f"{rec.allocated_execution:<10.1f} | {rec.achieved_execution:<10.1f} | "
            f"{rec.achieved_service_fraction:<12.2f} | {rec.utility:<8.1f} | {rec.achieved_utility:<12.2f}"
        )

    print("\n--- Service Allocation Timeline ---")
    service_events = [entry for entry in sim.timeline if "SERVICE" in entry[1] or "MODE" in entry[1] or "completed" in entry[1] or "released" in entry[1]]
    for t, event in sim.timeline:
        if "MODE" in event or "SERVICE" in event:
            print(f"  t = {t:6.2f} ms: {event}")

    return summary


if __name__ == "__main__":
    res_degraded = run_and_print_scheduler(
        name="EDF-VD + Degraded LO Service (Uniform 50%)",
        utility_aware=False,
        degraded_service_level=0.50,
    )

    print("\n\n")

    res_utility = run_and_print_scheduler(
        name="EDF-VD + Utility-Aware Degradation",
        utility_aware=True,
    )

    print("\n" + "=" * 80)
    print("COMPARATIVE SUMMARY:")
    print("=" * 80)
    print(f"EDF-VD + Degraded LO Service:     LO Utility Ratio = {res_degraded['LO_utility_ratio']:.4f} (Utility = {res_degraded['LO_utility']:.1f})")
    print(f"EDF-VD + Utility-Aware Degradation: LO Utility Ratio = {res_utility['LO_utility_ratio']:.4f} (Utility = {res_utility['LO_utility']:.1f})")
    diff = res_utility['LO_utility_ratio'] - res_degraded['LO_utility_ratio']
    print(f"Utility Gain from Density Ranking: {diff * 100:+.2f}%")
