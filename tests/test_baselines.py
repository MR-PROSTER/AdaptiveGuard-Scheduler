import pytest
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.simulation import Simulation
from config.default_config import SimulationConfig
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.flexible_mc import FlexibleMCScheduler


def test_classical_reactive_mc_initial_and_mode_switch():
    """Verify Classical Reactive MC initial mode LO and mode switch to HI dropping LO tasks."""
    scheduler = ClassicalReactiveMCScheduler()
    assert scheduler.current_mode == Criticality.LO

    tasks = get_stress_20ms_workload()
    j_hi = tasks[0].generate_job(0)
    j_lo = tasks[2].generate_job(0)

    scheduler.add_job(j_hi)
    scheduler.add_job(j_lo)
    assert len(scheduler.ready_queue) == 2

    # Transition to HI mode
    scheduler.set_mode(Criticality.HI)
    assert scheduler.current_mode == Criticality.HI
    assert len(scheduler.ready_queue) == 1
    assert scheduler.ready_queue[0] == j_hi

    # Adding new LO job in HI mode should be rejected/dropped
    j_lo_new = tasks[3].generate_job(0)
    scheduler.add_job(j_lo_new)
    assert len(scheduler.ready_queue) == 1


def test_degraded_edf_vd_service_levels():
    """Verify supported service levels and scaling in EDF-VD + Degraded LO Service."""
    tasks = get_stress_20ms_workload()
    scheduler = EDFVDDegradedScheduler(tasks=tasks, degraded_service_level=0.50)

    # Invalid service level raises ValueError
    with pytest.raises(ValueError, match="Unsupported degraded service level"):
        EDFVDDegradedScheduler(tasks=tasks, degraded_service_level=0.33)

    j_lo = tasks[2].generate_job(0, execution_budget=6.0)  # Telemetry C_LO=6.0
    scheduler.add_job(j_lo)

    # Mode switch to HI mode with 50% degraded service level
    scheduler.set_mode(Criticality.HI)
    assert j_lo.required_execution == 3.0  # 6.0 * 0.50 = 3.0
    assert j_lo.remaining_execution == 3.0


def test_flexible_mc_independent_escalation():
    """
    Verify Flexible MC task-level escalation:
    If H1 overruns, H1 escalates while H2 does NOT automatically escalate.
    """
    tasks = get_stress_20ms_workload()
    scheduler = FlexibleMCScheduler(tasks=tasks)

    h1 = tasks[0]  # Flight_Control (Task 1)
    h2 = tasks[1]  # Braking_Control (Task 2)

    assert scheduler.is_task_escalated(h1) is False
    assert scheduler.is_task_escalated(h2) is False

    # H1 overruns C_LO
    scheduler.on_task_overrun(h1)

    # H1 escalates independently
    assert scheduler.is_task_escalated(h1) is True
    # H2 does NOT automatically escalate
    assert scheduler.is_task_escalated(h2) is False

    # H2 later overruns C_LO
    scheduler.on_task_overrun(h2)
    assert scheduler.is_task_escalated(h2) is True


def test_baselines_simulation_h1_overrun_scenario():
    """Run Classical MC, EDF-VD Degraded, and Flexible MC on H1_OVERRUN scenario."""
    tasks = get_stress_20ms_workload()
    config = SimulationConfig(duration=40.0, verbose=False)

    # 1. Classical Reactive MC
    sim_class = Simulation(tasks=tasks, config=config, scheduler=ClassicalReactiveMCScheduler(), scenario=ExecutionScenario.H1_OVERRUN)
    res_class = sim_class.run()
    assert res_class["hi_missed_jobs_count"] == 0

    # 2. EDF-VD Degraded Service
    sim_degraded = Simulation(tasks=tasks, config=config, scheduler=EDFVDDegradedScheduler(tasks=tasks, degraded_service_level=0.50), scenario=ExecutionScenario.H1_OVERRUN)
    res_degraded = sim_degraded.run()
    assert res_degraded["hi_missed_jobs_count"] == 0

    # 3. Flexible MC
    sim_flex = Simulation(tasks=tasks, config=config, scheduler=FlexibleMCScheduler(tasks=tasks), scenario=ExecutionScenario.H1_OVERRUN)
    res_flex = sim_flex.run()
    assert res_flex["hi_missed_jobs_count"] == 0
