import pytest
from simulator.task import Task, Criticality
from workloads.fixed_workload import get_stress_20ms_workload
from controllers.mode_controller import SystemMode
from controllers.degradation_controller import (
    calculate_utility_density,
    rank_lo_tasks_by_utility_density,
    DegradationController,
)
from controllers.recovery_controller import (
    GradualRecoveryController,
    RECOVERY_STEPS,
)


def test_utility_density_calculation():
    """
    Test 1: Verify utility density calculation: utility / C_LO.
    For stress_20ms workload:
      - Telemetry (100 / 6 = 16.6667)
      - Logging_A (10 / 1 = 10.0)
      - Logging_B (10 / 1 = 10.0)
      - Logging_C (10 / 1 = 10.0)
    """
    tasks = get_stress_20ms_workload()
    task_dict = {t.name: t for t in tasks}

    telemetry = task_dict["Telemetry"]
    logging_a = task_dict["Logging_A"]

    assert pytest.approx(calculate_utility_density(telemetry), abs=1e-4) == 16.6667
    assert calculate_utility_density(logging_a) == 10.0


def test_lo_task_ranking_by_utility_density():
    """
    Test 2: Verify LO tasks are ranked in descending order of utility density.
    Telemetry (16.6667) must rank higher than Logging tasks (10.0).
    """
    tasks = get_stress_20ms_workload()
    ranked = rank_lo_tasks_by_utility_density(tasks)

    assert len(ranked) == 4
    # Telemetry should be ranked first due to highest utility density
    assert ranked[0].name == "Telemetry"
    assert calculate_utility_density(ranked[0]) == pytest.approx(16.6667, abs=1e-4)

    # Logging tasks follow
    for t in ranked[1:]:
        assert calculate_utility_density(t) == 10.0


def test_service_reduction_lower_density_first():
    """
    Test 3: Verify lower utility-density LO tasks are reduced FIRST in WARNING mode.
    Higher utility-density task (Telemetry) retains higher service than lower density logging tasks.
    """
    tasks = get_stress_20ms_workload()
    deg_controller = DegradationController(tasks=tasks)

    # In WARNING mode with moderate risk (e.g. risk = 0.70)
    service_levels = deg_controller.update(current_time=2.0, mode=SystemMode.WARNING, risk=0.70)

    task_dict = {t.name: t for t in tasks}
    telemetry_service = service_levels[task_dict["Telemetry"].task_id]
    logging_a_service = service_levels[task_dict["Logging_A"].task_id]
    logging_c_service = service_levels[task_dict["Logging_C"].task_id]

    # Telemetry must have higher or equal service level compared to lower density logging tasks
    assert telemetry_service >= logging_a_service
    assert telemetry_service >= logging_c_service


def test_hi_tasks_never_degraded():
    """
    Test 6: Verify HI-criticality tasks are NEVER degraded regardless of system mode or service requests.
    """
    tasks = get_stress_20ms_workload()
    deg_controller = DegradationController(tasks=tasks)

    h1 = tasks[0]  # Flight_Control (HI task)
    assert h1.criticality == Criticality.HI

    # Attempt to degrade H1 to 0.25
    deg_controller.set_task_service_level(current_time=1.0, task=h1, new_service=0.25, reason="Test HI degradation")

    # Service level must remain 1.00
    assert deg_controller.get_service_level(h1.task_id) == 1.00


def test_utility_metrics_calculation():
    """
    Test 4: Verify achieved_utility, LO_utility, maximum_possible_LO_utility, and LO_utility_ratio.
    """
    tasks = get_stress_20ms_workload()
    deg_controller = DegradationController(tasks=tasks)

    # Mock released and completed jobs where all LO tasks complete 100%
    lo_tasks = [t for t in tasks if t.criticality == Criticality.LO]
    released_jobs = [t.generate_job(0) for t in lo_tasks]
    completed_jobs = list(released_jobs)

    for j in completed_jobs:
        j.executed_time = j.required_execution
        j.completed = True

    metrics = deg_controller.calculate_utility_metrics(completed_jobs, released_jobs)

    # Telemetry(100) + Logging_A(10) + Logging_B(10) + Logging_C(10) = 130
    assert metrics["maximum_possible_LO_utility"] == 130.0
    assert metrics["LO_utility"] == 130.0
    assert metrics["LO_utility_ratio"] == 1.0


def test_gradual_recovery_steps():
    """
    Test 5: Verify gradual recovery restores LO task service step-by-step
    (0.00 -> 0.25 -> 0.50 -> 0.75 -> 1.00) rather than restoring everything at once.
    """
    tasks = get_stress_20ms_workload()
    deg_controller = DegradationController(tasks=tasks)

    # Set initial service to 0.00 in HI mode
    deg_controller.update(current_time=0.0, mode=SystemMode.HI, risk=0.85)
    for t in tasks:
        if t.criticality == Criticality.LO:
            assert deg_controller.get_service_level(t.task_id) == 0.00

    rec_controller = GradualRecoveryController(
        tasks=tasks,
        degradation_controller=deg_controller,
        step_interval=1.0,
    )

    # Enter RECOVERY mode at t=10.0
    services_t10 = rec_controller.update_recovery(current_time=10.0, mode=SystemMode.RECOVERY, risk=0.35)
    # Service levels should start low (e.g. 0.25 / 0.00) and NOT be immediately 1.00
    assert not all(s == 1.00 for s in services_t10.values())

    # Advance time to t=12.0 (2.0ms elapsed) -> service levels increase gradually
    services_t12 = rec_controller.update_recovery(current_time=12.0, mode=SystemMode.RECOVERY, risk=0.35)
    telemetry_id = [t.task_id for t in tasks if t.name == "Telemetry"][0]
    logging_id = [t.task_id for t in tasks if t.name == "Logging_A"][0]

    assert services_t12[telemetry_id] > services_t10[telemetry_id]
