import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from config.default_config import SimulationConfig
from simulator.simulation import Simulation

from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler

schedulers = [
    ("EDF", lambda tasks: EDFScheduler()),
    ("EDF-VD", lambda tasks: EDFVDScheduler(tasks=tasks)),
    ("Classical Reactive MC", lambda tasks: ClassicalReactiveMCScheduler()),
    ("EDF-VD + Degraded LO Service", lambda tasks: EDFVDDegradedScheduler(tasks=tasks, degraded_service_level=0.50)),
    ("Flexible MC", lambda tasks: FlexibleMCScheduler(tasks=tasks)),
    ("AdaptiveGuard", lambda tasks: AdaptiveGuardScheduler(tasks=tasks)),
]

print(f"{'Scheduler':<30} | {'HI Miss Ratio':<14} | {'LO Comp Ratio':<14} | {'LO Util Ratio':<14} | {'CPU Util':<10} | {'Mode Switches':<14} | {'Overhead (%)':<12}")
print("-" * 115)

for name, sched_factory in schedulers:
    tasks = get_stress_20ms_workload()
    sched = sched_factory(tasks)
    is_adaptive = (name == "AdaptiveGuard")
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
        monitor_interval=0.5,
        enable_monitoring=is_adaptive,
    )
    if is_adaptive:
        sim.mode_controller.warning_enter = 0.50
    summary = sim.run()

    hi_miss = summary["hi_miss_ratio"]
    lo_comp = summary["lo_completion_ratio"]
    lo_util = summary["LO_utility_ratio"]
    cpu_util = summary["cpu_utilization"]
    switches = summary["mode_switches_count"]
    overhead = summary["overhead_percentage"]

    print(f"{name:<30} | {hi_miss:<14.4f} | {lo_comp:<14.4f} | {lo_util:<14.4f} | {cpu_util:<10.4f} | {switches:<14} | {overhead:<12.4f}")
