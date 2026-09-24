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
from controllers.mode_controller import AdaptiveGuardModeController, SystemMode


def main() -> None:
    print("==================================================================")
    print(" AdaptiveGuard: Proactive and Graceful Mixed-Criticality Simulator")
    print(" AdaptiveGuard Mode Controller Evaluation")
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

    # Configure simulation for BOTH_OVERRUN scenario to demonstrate full mode transitions
    config = SimulationConfig(duration=40.0, cpu_speed=1.0, verbose=False)
    edf_scheduler = EDFScheduler()

    simulation = Simulation(
        tasks=taskset,
        config=config,
        scheduler=edf_scheduler,
        scenario=ExecutionScenario.BOTH_OVERRUN,
        monitor_interval=0.5,
        enable_monitoring=True,
    )

    print("Executing Fixed Workload (BOTH_OVERRUN Scenario) under AdaptiveGuard Mode Controller...")
    summary = simulation.run()
    print("Simulation Completed Successfully!\n")

    # Display Mode Controller Timeline (time, risk, mode)
    print("=" * 105)
    print(" ADAPTIVEGUARD MODE CONTROLLER EVALUATION TIMELINE (H1_OVERRUN SCENARIO)")
    print("=" * 105)
    print(f"{'time':<10} │ {'risk':<10} │ {'mode':<12} │ event / trigger")
    print("─" * 105)

    risk_history = summary["risk_history"]
    mode_controller = simulation.mode_controller
    transitions = mode_controller.transitions

    # Print timeline (time, risk, mode)
    for rm in risk_history:
        t = rm.timestamp
        risk_str = f"{rm.r_total:.4f}"
        
        # Determine mode active at timestamp t
        current_mode = "LO"
        for trans in transitions:
            if trans.time <= t:
                current_mode = trans.new_mode.value

        matching_trans = [tr for tr in transitions if abs(tr.time - t) < 1e-6]
        extra_info = rm.event_trigger
        if matching_trans:
            tr = matching_trans[0]
            extra_info = f"*** TRANSITION: {tr.old_mode.value} -> {tr.new_mode.value} ({tr.reason}) ***"

        print(f"{t:<10.2f} │ {risk_str:<10} │ {current_mode:<12} │ {extra_info}")

    print("=" * 105)
    print()

    # ------------------------------------------------------------------
    # DEMONSTRATION OF ALL MODE CONTROLLER TRANSITIONS & HYSTERESIS
    # ------------------------------------------------------------------
    print("Executing AdaptiveGuard Mode Controller Transition Sequence Demonstration...")
    demo_mc = AdaptiveGuardModeController(initial_mode=SystemMode.LO, recovery_hold_time=5.0)

    # Sequence of (time_ms, risk_score)
    risk_sequence = [
        (0.0, 0.20),   # Stay LO
        (1.0, 0.65),   # LO -> WARNING
        (2.0, 0.85),   # WARNING -> HI
        (3.0, 0.35),   # HI mode: risk drops <= 0.40 (timer starts at 3.0)
        (5.0, 0.35),   # HI mode: risk stays <= 0.40 (elapsed 2.0ms -> stay HI)
        (7.0, 0.35),   # HI mode: risk stays <= 0.40 (elapsed 4.0ms -> stay HI)
        (8.0, 0.35),   # HI mode: risk stays <= 0.40 (elapsed 5.0ms -> HI -> RECOVERY!)
        (9.0, 0.45),   # RECOVERY -> WARNING (risk > 0.40)
        (10.0, 0.30),  # WARNING -> LO (risk < 0.40)
    ]

    print("\n" + "=" * 80)
    print(" MODE CONTROLLER TRANSITION & HYSTERESIS DEMONSTRATION")
    print("=" * 80)
    print(f"{'time (ms)':<10} │ {'risk':<10} │ {'mode':<12} │ action / transition")
    print("─" * 80)

    for t, r in risk_sequence:
        prev_m = demo_mc.current_mode
        curr_m = demo_mc.update(t, r)
        trans_text = "Stay " + curr_m.value
        if prev_m != curr_m:
            last = demo_mc.transitions[-1]
            trans_text = f"*** TRANSITION: {last.old_mode.value} -> {last.new_mode.value} ({last.reason}) ***"
        print(f"{t:<10.1f} │ {r:<10.2f} │ {curr_m.value:<12} │ {trans_text}")

    print("=" * 80)
    print()


if __name__ == "__main__":
    main()
