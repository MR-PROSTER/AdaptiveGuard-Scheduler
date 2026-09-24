import pytest
from simulator.task import Criticality
from simulator.simulation import Simulation
from config.default_config import SimulationConfig
from workloads.fixed_workload import (
    WORKLOAD_NAME,
    ExecutionScenario,
    get_stress_20ms_workload,
    get_fixed_workload,
    calculate_hi_lo_utilization,
    calculate_lo_utilization,
    calculate_normal_utilization,
    calculate_worst_case_utilization,
    get_job_execution_requirement,
    print_workload_utilization,
)


def test_workload_name_and_task_definitions():
    """Verify workload name and exact task parameters for stress_20ms."""
    assert WORKLOAD_NAME == "stress_20ms"
    tasks = get_stress_20ms_workload()
    assert len(tasks) == 6

    # Convert to dict by task name for precise checks
    task_dict = {t.name: t for t in tasks}

    # H1: Flight_Control
    h1 = task_dict["Flight_Control"]
    assert h1.criticality == Criticality.HI
    assert h1.period == 20.0
    assert h1.relative_deadline == 20.0
    assert h1.C_LO == 2.0
    assert h1.C_HI == 6.0
    assert h1.utility == 0.0
    assert h1.minimum_service == 1.0
    assert h1.maximum_service == 1.0

    # H2: Braking_Control
    h2 = task_dict["Braking_Control"]
    assert h2.criticality == Criticality.HI
    assert h2.period == 20.0
    assert h2.relative_deadline == 20.0
    assert h2.C_LO == 3.0
    assert h2.C_HI == 7.0
    assert h2.utility == 0.0
    assert h2.minimum_service == 1.0
    assert h2.maximum_service == 1.0

    # L1: Telemetry
    l1 = task_dict["Telemetry"]
    assert l1.criticality == Criticality.LO
    assert l1.period == 20.0
    assert l1.relative_deadline == 20.0
    assert l1.C_LO == 6.0
    assert l1.C_HI == 6.0
    assert l1.utility == 100.0
    assert l1.minimum_service == 0.0
    assert l1.maximum_service == 1.0

    # L2: Logging_A
    l2 = task_dict["Logging_A"]
    assert l2.criticality == Criticality.LO
    assert l2.period == 20.0
    assert l2.relative_deadline == 20.0
    assert l2.C_LO == 1.0
    assert l2.C_HI == 1.0
    assert l2.utility == 10.0
    assert l2.minimum_service == 0.0
    assert l2.maximum_service == 1.0

    # L3: Logging_B
    l3 = task_dict["Logging_B"]
    assert l3.criticality == Criticality.LO
    assert l3.period == 20.0
    assert l3.relative_deadline == 20.0
    assert l3.C_LO == 1.0
    assert l3.C_HI == 1.0
    assert l3.utility == 10.0
    assert l3.minimum_service == 0.0
    assert l3.maximum_service == 1.0

    # L4: Logging_C
    l4 = task_dict["Logging_C"]
    assert l4.criticality == Criticality.LO
    assert l4.period == 20.0
    assert l4.relative_deadline == 20.0
    assert l4.C_LO == 1.0
    assert l4.C_HI == 1.0
    assert l4.utility == 10.0
    assert l4.minimum_service == 0.0
    assert l4.maximum_service == 1.0


def test_get_fixed_workload_alias():
    """Verify get_fixed_workload returns the same workload as get_stress_20ms_workload."""
    t1 = get_stress_20ms_workload()
    t2 = get_fixed_workload()
    assert len(t1) == len(t2)
    for a, b in zip(t1, t2):
        assert a.name == b.name
        assert a.C_LO == b.C_LO
        assert a.C_HI == b.C_HI


def test_utilization_values():
    """Verify exact utilization formulas and values."""
    tasks = get_stress_20ms_workload()

    hi_lo_util = calculate_hi_lo_utilization(tasks)
    lo_util = calculate_lo_utilization(tasks)
    normal_util = calculate_normal_utilization(tasks)
    worst_case_util = calculate_worst_case_utilization(tasks)

    # HI LO-assumption: 2/20 + 3/20 = 5/20 = 0.25
    assert pytest.approx(hi_lo_util, abs=1e-6) == 0.25

    # LO utilization: (6+1+1+1)/20 = 9/20 = 0.45
    assert pytest.approx(lo_util, abs=1e-6) == 0.45

    # Normal total utilization: 0.70
    assert pytest.approx(normal_util, abs=1e-6) == 0.70

    # Worst-case total utilization: (6+7+6+1+1+1)/20 = 22/20 = 1.10
    assert pytest.approx(worst_case_util, abs=1e-6) == 1.10


def test_print_workload_utilization(capsys):
    """Verify print_workload_utilization outputs expected text."""
    print_workload_utilization()
    captured = capsys.readouterr().out
    assert "HI LO-assumption utilization:" in captured
    assert "0.25" in captured
    assert "LO utilization:" in captured
    assert "0.45" in captured
    assert "Normal total utilization:" in captured
    assert "0.70" in captured
    assert "Worst-case total utilization:" in captured
    assert "1.10" in captured
    assert "intentionally normal-load feasible but worst-case overloaded" in captured


def test_scenario_normal():
    """Verify NORMAL execution scenario."""
    tasks = get_stress_20ms_workload()
    task_dict = {t.name: t for t in tasks}

    assert get_job_execution_requirement(task_dict["Flight_Control"], 0, ExecutionScenario.NORMAL) == 2.0
    assert get_job_execution_requirement(task_dict["Braking_Control"], 0, ExecutionScenario.NORMAL) == 3.0
    assert get_job_execution_requirement(task_dict["Telemetry"], 0, ExecutionScenario.NORMAL) == 6.0
    assert get_job_execution_requirement(task_dict["Logging_A"], 0, ExecutionScenario.NORMAL) == 1.0


def test_scenario_h1_overrun():
    """Verify H1_OVERRUN execution scenario."""
    tasks = get_stress_20ms_workload()
    task_dict = {t.name: t for t in tasks}

    assert get_job_execution_requirement(task_dict["Flight_Control"], 0, ExecutionScenario.H1_OVERRUN) == 6.0
    assert get_job_execution_requirement(task_dict["Braking_Control"], 0, ExecutionScenario.H1_OVERRUN) == 3.0
    assert get_job_execution_requirement(task_dict["Telemetry"], 0, ExecutionScenario.H1_OVERRUN) == 6.0


def test_scenario_both_overrun():
    """Verify BOTH_OVERRUN execution scenario."""
    tasks = get_stress_20ms_workload()
    task_dict = {t.name: t for t in tasks}

    assert get_job_execution_requirement(task_dict["Flight_Control"], 0, ExecutionScenario.BOTH_OVERRUN) == 6.0
    assert get_job_execution_requirement(task_dict["Braking_Control"], 0, ExecutionScenario.BOTH_OVERRUN) == 7.0
    assert get_job_execution_requirement(task_dict["Telemetry"], 0, ExecutionScenario.BOTH_OVERRUN) == 6.0


def test_scenario_bursty_reproducible():
    """Verify BURSTY execution scenario with fixed seed produces reproducible requirements."""
    tasks = get_stress_20ms_workload()
    task_dict = {t.name: t for t in tasks}

    h1 = task_dict["Flight_Control"]
    h2 = task_dict["Braking_Control"]
    l1 = task_dict["Telemetry"]

    reqs_h1_run1 = [get_job_execution_requirement(h1, seq, ExecutionScenario.BURSTY, seed=42) for seq in range(10)]
    reqs_h1_run2 = [get_job_execution_requirement(h1, seq, ExecutionScenario.BURSTY, seed=42) for seq in range(10)]
    assert reqs_h1_run1 == reqs_h1_run2
    assert all(r in (2.0, 6.0) for r in reqs_h1_run1)

    reqs_h2 = [get_job_execution_requirement(h2, seq, ExecutionScenario.BURSTY, seed=42) for seq in range(10)]
    assert all(r in (3.0, 7.0) for r in reqs_h2)

    # LO task always receives C_LO
    reqs_l1 = [get_job_execution_requirement(l1, seq, ExecutionScenario.BURSTY, seed=42) for seq in range(10)]
    assert all(r == 6.0 for r in reqs_l1)


def test_scenario_recovery():
    """Verify RECOVERY execution scenario transitions from overload to normal."""
    tasks = get_stress_20ms_workload()
    task_dict = {t.name: t for t in tasks}

    h1 = task_dict["Flight_Control"]
    h2 = task_dict["Braking_Control"]

    # Initial overloaded period (seq 0, 1, 2)
    for seq in range(3):
        assert get_job_execution_requirement(h1, seq, ExecutionScenario.RECOVERY, overload_until_seq=3) == 6.0
        assert get_job_execution_requirement(h2, seq, ExecutionScenario.RECOVERY, overload_until_seq=3) == 7.0

    # Recovery period (seq >= 3)
    for seq in range(3, 6):
        assert get_job_execution_requirement(h1, seq, ExecutionScenario.RECOVERY, overload_until_seq=3) == 2.0
        assert get_job_execution_requirement(h2, seq, ExecutionScenario.RECOVERY, overload_until_seq=3) == 3.0


def test_execution_requirement_stored_per_job():
    """Verify required execution budget is stored per Job instance during Simulation."""
    tasks = get_stress_20ms_workload()
    config = SimulationConfig(duration=40.0)

    sim = Simulation(tasks=tasks, config=config, scenario=ExecutionScenario.H1_OVERRUN)
    sim.run()

    # Find released jobs for Flight_Control (H1) and Braking_Control (H2)
    completed_jobs = {j.job_id: j for j in sim.completed_jobs + sim.active_jobs}

    # H1 J0 and J1 should have required_execution = 6.0
    assert completed_jobs["T1_J0"].required_execution == 6.0
    assert completed_jobs["T1_J1"].required_execution == 6.0

    # H2 J0 and J1 should have required_execution = 3.0
    assert completed_jobs["T2_J0"].required_execution == 3.0
    assert completed_jobs["T2_J1"].required_execution == 3.0
