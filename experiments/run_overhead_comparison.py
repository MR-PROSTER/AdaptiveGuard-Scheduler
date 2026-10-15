"""
Overhead Comparison Evaluation Script.

Compares all mixed-criticality schedulers:
1. EDF
2. EDF-VD
3. Classical Reactive MC
4. EDF-VD + Degraded LO Service
5. Flexible MC
6. AdaptiveGuard

Under two conditions:
- Without Overhead (enable_overhead = False)
- With Overhead (enable_overhead = True: sched=0.01ms, risk=0.005ms, trans=0.01ms)

Metrics:
- HI miss ratio
- LO utility ratio
- Average response time
- CPU utilization
- Overhead percentage
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import List, Tuple, Callable
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from config.default_config import SimulationConfig
from simulator.simulation import Simulation
from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler


def evaluate_schedulers(scenario: ExecutionScenario = ExecutionScenario.BOTH_OVERRUN, duration: float = 40.0):
    scheduler_factories: List[Tuple[str, Callable]] = [
        ("EDF", lambda tasks: EDFScheduler()),
        ("EDF-VD", lambda tasks: EDFVDScheduler(tasks=tasks)),
        ("Classical Reactive MC", lambda tasks: ClassicalReactiveMCScheduler()),
        ("EDF-VD + Degraded LO", lambda tasks: EDFVDDegradedScheduler(tasks=tasks, degraded_service_level=0.50)),
        ("Flexible MC", lambda tasks: FlexibleMCScheduler(tasks=tasks)),
        ("AdaptiveGuard", lambda tasks: AdaptiveGuardScheduler(tasks=tasks)),
    ]

    results = []

    for name, factory in scheduler_factories:
        for enable_ovh in [False, True]:
            tasks = get_stress_20ms_workload()
            sched = factory(tasks)
            is_adaptive = (name == "AdaptiveGuard")

            config = SimulationConfig(
                duration=duration,
                verbose=False,
                enable_overhead=enable_ovh,
                scheduler_overhead=0.01,
                risk_estimation_overhead=0.005,
                mode_transition_overhead=0.01,
            )

            sim = Simulation(
                tasks=tasks,
                config=config,
                scheduler=sched,
                scenario=scenario,
                monitor_interval=0.5,
                enable_monitoring=is_adaptive,
            )

            summary = sim.run()

            results.append({
                "scheduler": name,
                "overhead_enabled": enable_ovh,
                "hi_miss_ratio": summary["hi_miss_ratio"],
                "lo_utility_ratio": summary["LO_utility_ratio"],
                "lo_completion_ratio": summary["lo_completion_ratio"],
                "avg_response_time": summary["average_response_time"],
                "cpu_utilization": summary["cpu_utilization"],
                "overhead_pct": summary["overhead_percentage"],
                "total_overhead_time": summary["total_overhead_time"],
                "sched_invocations": summary["scheduler_invocations"],
                "risk_calcs": summary["risk_calculations"],
                "mode_trans": summary["mode_transitions"],
                "sched_ovh_time": summary["scheduler_overhead_time"],
                "risk_ovh_time": summary["risk_overhead_time"],
                "trans_ovh_time": summary["mode_transition_overhead_time"],
            })

    return results


def print_comparison_table(results: List[dict]):
    print("=" * 135)
    print("COMPUTATIONAL OVERHEAD MODEL COMPARISON TABLE (Scenario: BOTH_OVERRUN, Duration: 40ms)")
    print("Overhead Config: sched_overhead = 0.01 ms | risk_overhead = 0.005 ms | mode_trans_overhead = 0.01 ms")
    print("=" * 135)

    header = (
        f"{'Scheduler':<24} | {'Overhead Mode':<14} | {'HI Miss Ratio':<14} | "
        f"{'LO Util Ratio':<14} | {'Resp Time (ms)':<15} | {'CPU Util':<10} | {'Overhead (%)':<12}"
    )
    print(header)
    print("-" * 135)

    for r in results:
        ovh_label = "With Overhead" if r["overhead_enabled"] else "No Overhead"
        print(
            f"{r['scheduler']:<24} | {ovh_label:<14} | {r['hi_miss_ratio']:<14.4f} | "
            f"{r['lo_utility_ratio']:<14.4f} | {r['avg_response_time']:<15.2f} | "
            f"{r['cpu_utilization']:<10.4f} | {r['overhead_pct']:<12.4f}"
        )

    print("\n" + "=" * 135)
    print("DETAILED OVERHEAD ACCOUNTING BREAKDOWN (When enable_overhead = True)")
    print("=" * 135)
    detail_header = (
        f"{'Scheduler':<24} | {'Sched Invoc':<12} | {'Risk Calcs':<11} | {'Mode Trans':<11} | "
        f"{'Sched Ovh(ms)':<14} | {'Risk Ovh(ms)':<13} | {'Trans Ovh(ms)':<14} | {'Total Ovh(ms)':<14}"
    )
    print(detail_header)
    print("-" * 135)

    for r in results:
        if r["overhead_enabled"]:
            print(
                f"{r['scheduler']:<24} | {r['sched_invocations']:<12} | {r['risk_calcs']:<11} | {r['mode_trans']:<11} | "
                f"{r['sched_ovh_time']:<14.4f} | {r['risk_ovh_time']:<13.4f} | {r['trans_ovh_time']:<14.4f} | "
                f"{r['total_overhead_time']:<14.4f}"
            )
    print("=" * 135)


if __name__ == "__main__":
    res = evaluate_schedulers(ExecutionScenario.BOTH_OVERRUN, duration=40.0)
    print_comparison_table(res)
