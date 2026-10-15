"""
Execution and Instrumentation Script for AdaptiveGuard Scheduler across 4 Scenarios:
1. NORMAL
2. H1_OVERRUN
3. BOTH_OVERRUN
4. RECOVERY
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Dict, Any, List
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from config.default_config import SimulationConfig
from simulator.simulation import Simulation
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from controllers.mode_controller import SystemMode


def run_and_report_scenario(scenario: ExecutionScenario, duration: float = 20.0) -> Dict[str, Any]:
    print("=" * 105)
    print(f"RUNNING SCENARIO: {scenario.name} (Duration: {duration:.1f}ms)")
    print("=" * 105)

    tasks = get_stress_20ms_workload()
    scheduler = AdaptiveGuardScheduler(tasks=tasks)
    config = SimulationConfig(duration=duration, verbose=False, enable_overhead=False)

    sim = Simulation(
        tasks=tasks,
        config=config,
        scheduler=scheduler,
        scenario=scenario,
        monitor_interval=0.5,
        enable_monitoring=True,
    )
    summary = sim.run()

    print("\n--- Scheduling Decisions Timeline ---")
    print(
        f"{'Time(ms)':>8} | {'Mode':<8} | {'Risk':<6} | {'Selected':<8} | {'Crit':<4} | {'Deadline':<8} | {'Laxity':<8} | {'LO Allocations':<32} | {'Reason'}"
    )
    print("-" * 140)

    # Print representative decisions (deduplicated consecutive idle/running if identical)
    last_print = None
    for d in summary["scheduling_decisions"]:
        t = d["time"]
        mode = d["mode"]
        risk = d["risk"]
        sel = d["selected_job"]
        crit = d["selected_job_criticality"]
        ddl = f"{d['selected_job_deadline']:.2f}" if d["selected_job_deadline"] is not None else "N/A"
        lax = f"{d['selected_job_laxity']:.2f}" if d["selected_job_laxity"] is not None else "N/A"
        alloc_str = ", ".join(f"{k}={v:.2f}" for k, v in d["lo_service_allocations"].items())
        reason = d["reason"]

        curr_print = (mode, sel, crit, alloc_str, reason)
        if curr_print != last_print or t in (0.0, 2.0, 6.0, 13.0, 20.0):
            print(
                f"{t:8.2f} | {mode:<8} | {risk:6.4f} | {sel:<8} | {crit:<4} | {ddl:>8} | {lax:>8} | {alloc_str:<32} | {reason}"
            )
            last_print = curr_print

    print("\n--- Summary Metrics ---")
    print(f"HI Miss Ratio:       {summary['hi_miss_ratio']:.4f} ({summary['hi_missed_jobs_count']}/{summary['hi_released_jobs_count']})")
    print(f"LO Completion Ratio: {summary['lo_completion_ratio']:.4f} ({summary['lo_completed_jobs_count']}/{summary['lo_released_jobs_count']})")
    print(f"LO Utility Achieved: {summary['LO_utility']:.2f} / {summary['maximum_possible_LO_utility']:.2f}")
    print(f"LO Utility Ratio:    {summary['LO_utility_ratio']:.4f}")
    print(f"CPU Utilization:     {summary['cpu_utilization']:.4f}")
    print(f"Mode Transitions:    {summary['mode_switches_count']}")
    if summary["mode_switches_count"] > 0:
        print("Recorded Mode Transitions:")
        for tr in sim.mode_controller.transitions:
            print(f"  t={tr.timestamp:5.2f}ms: {tr.old_mode.name} -> {tr.new_mode.name} | Risk={tr.risk:.4f} (Util={tr.r_util:.2f}, Lax={tr.r_laxity:.2f}, Ovr={tr.r_overrun:.2f}, Ddl={tr.r_deadline:.2f}) | {tr.reason}")

    return summary


def main():
    scenarios = [
        (ExecutionScenario.NORMAL, 20.0),
        (ExecutionScenario.H1_OVERRUN, 20.0),
        (ExecutionScenario.BOTH_OVERRUN, 20.0),
        (ExecutionScenario.RECOVERY, 80.0),
    ]
    for sc, dur in scenarios:
        run_and_report_scenario(sc, dur)
        print("\n")


if __name__ == "__main__":
    main()
