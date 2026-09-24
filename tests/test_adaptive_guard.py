"""
Unit tests for AdaptiveGuard Scheduler and Simulated Overhead Accounting.
"""

import pytest
from simulator.task import Task, Criticality
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from config.default_config import SimulationConfig
from simulator.simulation import Simulation
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from schedulers.proactive_risk_mc import ProactiveRiskMCScheduler
from schedulers.edf import EDFScheduler
from controllers.mode_controller import SystemMode


def test_adaptive_guard_scheduler_creation():
    """Verify initialization and virtual deadline calculation for AdaptiveGuardScheduler."""
    tasks = get_stress_20ms_workload()
    scheduler = AdaptiveGuardScheduler(tasks=tasks)

    assert scheduler.name == "AdaptiveGuard"
    assert pytest.approx(scheduler.x, abs=1e-4) == 0.4545
    assert scheduler.current_mode == SystemMode.LO


def test_adaptive_guard_control_loop_execution():
    """Verify full control loop execution of AdaptiveGuard in Simulation."""
    tasks = get_stress_20ms_workload()
    scheduler = AdaptiveGuardScheduler(tasks=tasks)
    config = SimulationConfig(duration=40.0, verbose=False)

    sim = Simulation(
        tasks=tasks,
        config=config,
        scheduler=scheduler,
        scenario=ExecutionScenario.BOTH_OVERRUN,
        enable_monitoring=True,
    )
    summary = sim.run()

    assert summary["scheduler"] == "AdaptiveGuard"
    assert "LO_utility" in summary
    assert summary["total_jobs_released"] > 0
    assert summary["completed_jobs_count"] > 0


def test_simulated_overhead_accounting():
    """Verify overhead accounting when enable_overhead is True vs False."""
    tasks = get_stress_20ms_workload()
    config_free = SimulationConfig(duration=40.0, enable_overhead=False)
    config_overhead = SimulationConfig(
        duration=40.0,
        enable_overhead=True,
        scheduler_overhead=0.01,
        risk_estimation_overhead=0.005,
        mode_transition_overhead=0.01,
    )

    sim_free = Simulation(tasks=tasks, config=config_free, scheduler=EDFScheduler())
    summary_free = sim_free.run()
    assert summary_free["total_overhead"] == 0.0
    assert summary_free["overhead_percentage"] == 0.0

    sim_overhead = Simulation(tasks=tasks, config=config_overhead, scheduler=EDFScheduler())
    summary_overhead = sim_overhead.run()

    assert summary_overhead["scheduler_decision_count"] > 0
    assert summary_overhead["risk_calculation_count"] > 0
    assert summary_overhead["total_overhead"] > 0.0
    assert summary_overhead["overhead_percentage"] > 0.0


def test_all_schedulers_instantiation():
    """Verify all 7 schedulers can be instantiated and initialized."""
    tasks = get_stress_20ms_workload()
    from schedulers.edf import EDFScheduler
    from schedulers.edf_vd import EDFVDScheduler
    from schedulers.classical_mc import ClassicalReactiveMCScheduler
    from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
    from schedulers.flexible_mc import FlexibleMCScheduler

    schedulers = [
        EDFScheduler(),
        EDFVDScheduler(tasks=tasks),
        ClassicalReactiveMCScheduler(),
        EDFVDDegradedScheduler(tasks=tasks),
        FlexibleMCScheduler(tasks=tasks),
        ProactiveRiskMCScheduler(tasks=tasks),
        AdaptiveGuardScheduler(tasks=tasks),
    ]

    assert len(schedulers) == 7
    for s in schedulers:
        assert s.name is not None
