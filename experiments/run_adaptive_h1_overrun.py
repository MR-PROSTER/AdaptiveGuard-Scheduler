import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from config.default_config import SimulationConfig
from simulator.simulation import Simulation
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler
from schedulers.classical_mc import ClassicalReactiveMCScheduler


def run_scenario(scenario_name: ExecutionScenario, title: str):
    print("=" * 105)
    print(f"ADAPTIVEGUARD TIMELINE EVALUATION: {title}")
    print("=" * 105)

    tasks = get_stress_20ms_workload()
    sched = AdaptiveGuardScheduler(tasks=tasks)
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
        scenario=scenario_name,
        monitor_interval=0.5,
        enable_monitoring=True,
    )

    summary = sim.run()

    print(f"\n{'Time (ms)':<10} | {'Running Job':<12} | {'Risk (R_tot)':<12} | {'Mode':<10} | {'Service Levels (Telemetry, LogA, LogB, LogC)':<45}")
    print("-" * 105)

    last_time = -1.0
    for snap in summary["state_timeline"]:
        t = snap["time"]
        # Filter to avoid duplicate lines at exact same timestamp if needed, but display all key transitions
        serv = snap["service_levels"]
        serv_str = f"L1(Telem)={serv.get('L1', 1.0):.2f}, L2={serv.get('L2', 1.0):.2f}, L3={serv.get('L3', 1.0):.2f}, L4={serv.get('L4', 1.0):.2f}"
        print(f"{t:10.2f} | {snap['running_job']:<12} | {snap['risk']:<12.4f} | {snap['mode']:<10} | {serv_str:<45}")

    print("\n--- Summary Metrics ---")
    print(f"HI Miss Ratio:       {summary['hi_miss_ratio']:.4f} ({summary['hi_missed_jobs_count']}/{summary['hi_released_jobs_count']})")
    print(f"LO Completion Ratio: {summary['lo_completion_ratio']:.4f} ({summary['lo_completed_jobs_count']}/{summary['lo_released_jobs_count']})")
    print(f"LO Utility Achieved: {summary['LO_utility']:.2f} / {summary['maximum_possible_LO_utility']:.2f}")
    print(f"LO Utility Ratio:    {summary['LO_utility_ratio']:.4f}")
    print(f"CPU Utilization:     {summary['cpu_utilization']:.4f}")
    print(f"Mode Transitions:    {len(sim.mode_controller.transitions)}")

    if sim.mode_controller.transitions:
        print("\n--- Recorded Mode Transitions ---")
        for tr in sim.mode_controller.transitions:
            print(f"  t = {tr.time:6.2f} ms: {tr.old_mode.value} -> {tr.new_mode.value} | Risk={tr.risk:.4f} (util={tr.r_util:.2f}, lax={tr.r_laxity:.2f}, ovr={tr.r_overrun:.2f}, ddl={tr.r_deadline:.2f}) | Reason: {tr.reason}")
    else:
        print("\n--- Recorded Mode Transitions: None (System remained in LO mode) ---")

    return summary


if __name__ == "__main__":
    # Primary required run: H1_OVERRUN
    run_scenario(ExecutionScenario.H1_OVERRUN, "H1_OVERRUN SCENARIO (Flight_Control overruns to C_HI=6.0)")

    print("\n\n")

    # Secondary comparison run: BOTH_OVERRUN (where severe overload occurs)
    run_scenario(ExecutionScenario.BOTH_OVERRUN, "BOTH_OVERRUN SCENARIO (H1 and H2 both overrun to C_HI)")
