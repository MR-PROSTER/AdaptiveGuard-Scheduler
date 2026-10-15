"""
Tests for Utility-Aware Degradation Component.

Verifies:
1. Higher utility-density tasks are preferred.
2. Low-value tasks are degraded before high-value tasks.
3. Service fractions actually affect execution.
4. Utility metrics change when degradation changes.
5. HI tasks are never degraded.
"""

import pytest
from simulator.task import Task, Criticality
from workloads.fixed_workload import get_stress_20ms_workload
from controllers.mode_controller import SystemMode
from controllers.degradation_controller import (
    calculate_utility_density,
    rank_lo_tasks_by_utility_density,
    DegradationController,
)


def test_higher_utility_density_preferred():
    """
    Test 1: Higher utility-density tasks are preferred.
    Tests both arbitrary tasksets and the stress_20ms workload.
    """
    # 1. Arbitrary taskset:
    task_a = Task(task_id=1, name="LO_A", criticality=Criticality.LO, period=20.0, relative_deadline=20.0, C_LO=4.0, C_HI=4.0, utility=20.0)
    task_b = Task(task_id=2, name="LO_B", criticality=Criticality.LO, period=20.0, relative_deadline=20.0, C_LO=2.0, C_HI=2.0, utility=80.0)
    task_c = Task(task_id=3, name="LO_C", criticality=Criticality.LO, period=20.0, relative_deadline=20.0, C_LO=3.0, C_HI=3.0, utility=30.0)

    tasks = [task_a, task_b, task_c]
    ranked = rank_lo_tasks_by_utility_density(tasks)
    assert ranked[0].name == "LO_B"  # density: 80 / 2 = 40.0
    assert ranked[1].name == "LO_C"  # density: 30 / 3 = 10.0
    assert ranked[2].name == "LO_A"  # density: 20 / 4 = 5.0

    # With capacity only enough for 0.12 (Task B requires 2/20 = 0.10):
    controller = DegradationController(tasks=tasks)
    allocations = controller.allocate_service_levels(available_capacity=0.12)
    assert allocations[task_b.task_id] == 1.00
    assert allocations[task_c.task_id] == 0.00
    assert allocations[task_a.task_id] == 0.00

    # 2. stress_20ms workload:
    stress_tasks = get_stress_20ms_workload()
    stress_ranked = rank_lo_tasks_by_utility_density(stress_tasks)
    assert stress_ranked[0].name == "Telemetry"
    assert pytest.approx(calculate_utility_density(stress_ranked[0]), abs=1e-3) == 16.667
    for t in stress_ranked[1:]:
        assert calculate_utility_density(t) == 10.0


def test_low_value_tasks_degraded_before_high_value_tasks():
    """
    Test 2: Low-value tasks are degraded before high-value tasks.
    As capacity constrains, lowest utility-density tasks drop to lower service levels first.
    """
    tasks = get_stress_20ms_workload()
    controller = DegradationController(tasks=tasks)
    task_dict = {t.name: t for t in tasks}

    telem = task_dict["Telemetry"]
    log_a = task_dict["Logging_A"]
    log_b = task_dict["Logging_B"]
    log_c = task_dict["Logging_C"]

    # When available capacity = 0.35 (nominal HI mode remaining capacity)
    # Telemetry (U=0.30) + Logging_A (U=0.05) fit; Logging_B and Logging_C cannot fit
    alloc_035 = controller.allocate_service_levels(available_capacity=0.35)
    assert alloc_035[telem.task_id] == 1.00
    assert alloc_035[log_a.task_id] == 1.00
    assert alloc_035[log_b.task_id] == 0.00
    assert alloc_035[log_c.task_id] == 0.00

    # When capacity shrinks further to 0.25:
    # Telemetry (U=0.30) gets 0.75 (load 0.225), rem cap 0.025 -> Logging_A gets 0.50 (load 0.025)
    # Logging_B and Logging_C are shed to 0.00
    alloc_025 = controller.allocate_service_levels(available_capacity=0.25)
    assert alloc_025[telem.task_id] == 0.75
    assert alloc_025[log_a.task_id] == 0.50
    assert alloc_025[log_b.task_id] == 0.00
    assert alloc_025[log_c.task_id] == 0.00

    # When capacity shrinks to 0.15:
    # Telemetry gets 0.50 (load 0.15), all logging tasks get 0.00
    alloc_015 = controller.allocate_service_levels(available_capacity=0.15)
    assert alloc_015[telem.task_id] == 0.50
    assert alloc_015[log_a.task_id] == 0.00
    assert alloc_015[log_b.task_id] == 0.00
    assert alloc_015[log_c.task_id] == 0.00

    # Highest density task (Telemetry) service is strictly higher than lowest density tasks
    assert alloc_015[telem.task_id] > alloc_015[log_c.task_id]


def test_service_fractions_affect_execution():
    """
    Test 3: Service fractions actually affect execution.
    Verify that scaling service fraction scales required execution, remaining execution,
    and actual executed CPU time.
    """
    tasks = get_stress_20ms_workload()
    telemetry_task = [t for t in tasks if t.name == "Telemetry"][0]

    # At full service (1.00): execution is C_LO = 6.0
    job_full = telemetry_task.generate_job(sequence_num=0)
    assert job_full.nominal_execution == 6.0
    assert job_full.required_execution == 6.0
    assert job_full.remaining_execution == 6.0

    # At degraded service (0.50): execution is 3.0
    job_half = telemetry_task.generate_job(sequence_num=1, execution_budget=telemetry_task.C_LO * 0.50)
    assert job_half.nominal_execution == 6.0
    assert job_half.required_execution == 3.0
    assert job_half.remaining_execution == 3.0

    # At degraded service (0.25): execution is 1.5
    job_quarter = telemetry_task.generate_job(sequence_num=2, execution_budget=telemetry_task.C_LO * 0.25)
    assert job_quarter.nominal_execution == 6.0
    assert job_quarter.required_execution == 1.5
    assert job_quarter.remaining_execution == 1.5

    # At degraded service (0.00): execution is 0.0
    job_zero = telemetry_task.generate_job(sequence_num=3, execution_budget=0.0)
    assert job_zero.nominal_execution == 6.0
    assert job_zero.required_execution == 0.0
    assert job_zero.remaining_execution == 0.0


def test_utility_metrics_change_when_degradation_changes():
    """
    Test 4: Utility metrics change when degradation changes.
    Tracks:
      - requested execution
      - allocated execution
      - achieved service fraction
      - utility
      - achieved utility
    And verifies that utility under utility-aware degradation differs from uniform degradation.
    """
    tasks = get_stress_20ms_workload()
    controller = DegradationController(tasks=tasks)
    lo_tasks = [t for t in tasks if t.criticality == Criticality.LO]

    # Scenario A: Full service (1.00)
    rel_a = [t.generate_job(0) for t in lo_tasks]
    comp_a = []
    for j in rel_a:
        j.executed_time = j.required_execution
        comp_a.append(j)
    metrics_a = controller.calculate_utility_metrics(comp_a, rel_a)
    assert metrics_a["LO_utility"] == 130.0
    assert metrics_a["LO_utility_ratio"] == 1.0

    # Scenario B: Uniform 50% degradation
    rel_b = [t.generate_job(0, execution_budget=t.C_LO * 0.50) for t in lo_tasks]
    comp_b = []
    for j in rel_b:
        j.executed_time = j.required_execution
        comp_b.append(j)
    metrics_b = controller.calculate_utility_metrics(comp_b, rel_b)
    # Telemetry: 100 * 0.5 = 50. Log A,B,C: 10 * 0.5 = 5 each. Total = 65.0
    assert metrics_b["LO_utility"] == 65.0
    assert metrics_b["LO_utility_ratio"] == 0.50

    # Scenario C: Utility-aware degradation under HI mode capacity constraint (avail_cap=0.35)
    # Telemetry gets 1.00, Logging_A gets 1.00, Logging_B gets 0.00, Logging_C gets 0.00
    alloc_c = controller.allocate_service_levels(available_capacity=0.35)
    rel_c = []
    comp_c = []
    for t in lo_tasks:
        s = alloc_c[t.task_id]
        j = t.generate_job(0, execution_budget=t.C_LO * s)
        j.executed_time = t.C_LO * s
        rel_c.append(j)
        if s > 0.0:
            comp_c.append(j)
    metrics_c = controller.calculate_utility_metrics(comp_c, rel_c)
    # Telemetry: 100 * 1.0 = 100. Log A: 10 * 1.0 = 10. Total = 110.0
    assert metrics_c["LO_utility"] == 110.0
    assert pytest.approx(metrics_c["LO_utility_ratio"], abs=1e-3) == (110.0 / 130.0)

    # Verify per-task tracking reports
    reports = metrics_c["task_reports"]
    assert len(reports) == 4
    telem_report = [r for r in reports.values() if r.task_name == "Telemetry"][0]
    assert telem_report.requested_execution == 6.0
    assert telem_report.allocated_execution == 6.0
    assert telem_report.achieved_execution == 6.0
    assert telem_report.achieved_service_fraction == 1.0
    assert telem_report.utility == 100.0
    assert telem_report.achieved_utility == 100.0

    log_c_report = [r for r in reports.values() if r.task_name == "Logging_C"][0]
    assert log_c_report.requested_execution == 1.0
    assert log_c_report.allocated_execution == 0.0
    assert log_c_report.achieved_execution == 0.0
    assert log_c_report.achieved_service_fraction == 0.0
    assert log_c_report.utility == 10.0
    assert log_c_report.achieved_utility == 0.0

    # Confirm utility metrics change across scenarios
    assert metrics_a["LO_utility"] > metrics_c["LO_utility"] > metrics_b["LO_utility"]


def test_hi_tasks_never_degraded():
    """
    Test 5: HI tasks are never degraded.
    In all modes and under all capacity conditions, HI tasks maintain service level 1.00.
    """
    tasks = get_stress_20ms_workload()
    controller = DegradationController(tasks=tasks)
    hi_tasks = [t for t in tasks if t.criticality == Criticality.HI]

    assert len(hi_tasks) == 2

    for hi in hi_tasks:
        # Default service level
        assert controller.get_service_level(hi.task_id) == 1.00

        # Attempt to degrade directly
        controller.set_task_service_level(current_time=1.0, task=hi, new_service=0.25, reason="Direct attempt")
        assert controller.get_service_level(hi.task_id) == 1.00

        controller.set_task_service_level(current_time=2.0, task=hi, new_service=0.00, reason="Direct drop attempt")
        assert controller.get_service_level(hi.task_id) == 1.00

    # Even in HI mode with 0.0 available LO capacity
    controller.update(current_time=5.0, mode=SystemMode.HI, risk=1.0, available_capacity=0.0)
    for hi in hi_tasks:
        assert controller.get_service_level(hi.task_id) == 1.00
