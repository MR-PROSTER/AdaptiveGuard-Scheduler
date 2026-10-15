"""
Unit tests validating correctness fixes for:
1. Job release handling
2. Absolute deadline calculation
3. Remaining execution tracking
4. Preemption
5. Deadline miss detection
6. EDF priority ordering
7. EDF-VD virtual deadline calculation
8. LO/HI mode propagation
9. Runtime monitor state
10. Risk calculation
11. Service-level tracking
12. Metric calculation
"""

import pytest
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.simulation import Simulation
from config.default_config import SimulationConfig
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario

from schedulers.edf import EDFScheduler
from schedulers.edf_vd import EDFVDScheduler, virtual_deadline, calculate_x
from schedulers.classical_mc import ClassicalReactiveMCScheduler
from schedulers.degraded_edf_vd import EDFVDDegradedScheduler
from schedulers.adaptive_guard import AdaptiveGuardScheduler

from controllers.mode_controller import (
    SystemMode,
    AdaptiveGuardModeController,
    is_hi_mode,
    is_lo_mode,
)
from controllers.runtime_monitor import RuntimeMonitor
from controllers.risk_estimator import RiskEstimator
from controllers.degradation_controller import DegradationController
from metrics.utility_metrics import calculate_utility_metrics


def test_fix_1_and_2_job_release_and_deadline_calculation():
    """Verify job release and absolute deadline calculation formulas with nominal execution preservation."""
    task = Task(
        task_id=1,
        name="TestTask",
        criticality=Criticality.HI,
        period=25.0,
        relative_deadline=20.0,
        C_LO=3.0,
        C_HI=8.0,
        release_offset=5.0,
    )
    job = task.generate_job(sequence_num=2, execution_budget=8.0)

    # release_time = offset + k * period = 5.0 + 2 * 25.0 = 55.0
    assert job.release_time == 55.0
    # absolute_deadline = release_time + relative_deadline = 55.0 + 20.0 = 75.0
    assert job.absolute_deadline == 75.0
    assert job.required_execution == 8.0
    assert job.remaining_execution == 8.0
    assert job.nominal_execution == 8.0


def test_fix_3_remaining_execution_tracking_under_degradation():
    """Verify remaining_execution tracking and scaling when degradation occurs."""
    task = Task(
        task_id=2,
        name="LOTask",
        criticality=Criticality.LO,
        period=20.0,
        relative_deadline=20.0,
        C_LO=6.0,
        C_HI=6.0,
    )
    job = task.generate_job(0)
    assert job.nominal_execution == 6.0
    assert job.remaining_execution == 6.0

    # Partially execute 2.0 ms
    exec_done = job.execute(2.0)
    assert exec_done == 2.0
    assert job.executed_time == 2.0
    assert job.remaining_execution == 4.0

    # Degrade to 50% service: target budget = 3.0 ms
    target_budget = task.C_LO * 0.50
    job.remaining_execution = max(0.0, target_budget - job.executed_time)
    assert job.remaining_execution == 1.0


def test_fix_4_preemption_and_overrun_scheduling():
    """Verify preemption and discrete overrun scheduling."""
    tasks = get_stress_20ms_workload()
    sim = Simulation(
        tasks=tasks,
        config=SimulationConfig(duration=40.0),
        scheduler=EDFVDScheduler(tasks=tasks),
        scenario=ExecutionScenario.BOTH_OVERRUN,
        enable_monitoring=False,
    )
    summary = sim.run()

    # Preemption and overrun mode change must trigger even with monitoring disabled
    assert summary["mode_switches_count"] >= 1
    assert any("MODE CHANGE" in event_str for _, event_str in summary["timeline"])


def test_fix_5_deadline_miss_detection():
    """Verify deadline miss flag is set correctly on job when deadline is reached without completion."""
    task = Task(
        task_id=3,
        name="StrictTask",
        criticality=Criticality.HI,
        period=10.0,
        relative_deadline=10.0,
        C_LO=2.0,
        C_HI=5.0,
    )
    job = task.generate_job(0)  # release=0, deadline=10
    assert not job.check_deadline(current_time=9.9)
    assert not job.missed_deadline

    # At current_time >= 10.0 without completion -> missed
    assert job.check_deadline(current_time=10.0)
    assert job.missed_deadline is True


def test_fix_6_edf_priority_ordering_filtering():
    """Verify EDFScheduler ignores completed or 0-remaining execution jobs."""
    scheduler = EDFScheduler()
    t1 = Task(task_id=1, name="H1", criticality=Criticality.HI, period=20.0, relative_deadline=20.0, C_LO=2.0, C_HI=5.0)
    j1 = t1.generate_job(0)
    j1.completed = True
    j1.remaining_execution = 0.0

    t2 = Task(task_id=2, name="H2", criticality=Criticality.HI, period=30.0, relative_deadline=30.0, C_LO=3.0, C_HI=6.0)
    j2 = t2.generate_job(0)

    scheduler.add_job(j1)
    scheduler.add_job(j2)

    assert scheduler.select_job(0.0) == j2


def test_fix_7_edf_vd_virtual_deadline_flexible_modes():
    """Verify EDF-VD virtual deadline calculation supports SystemMode as well as Criticality."""
    t_hi = Task(task_id=1, name="HI", criticality=Criticality.HI, period=20.0, relative_deadline=20.0, C_LO=2.0, C_HI=6.0)
    job = t_hi.generate_job(0)
    x = 0.5

    # In SystemMode.LO and SystemMode.WARNING -> virtual deadline
    vd_sys_lo = virtual_deadline(job, x, SystemMode.LO)
    assert vd_sys_lo == 10.0
    vd_sys_warn = virtual_deadline(job, x, SystemMode.WARNING)
    assert vd_sys_warn == 10.0

    # In SystemMode.HI -> actual deadline
    vd_sys_hi = virtual_deadline(job, x, SystemMode.HI)
    assert vd_sys_hi == 20.0


def test_fix_8_lo_hi_mode_propagation():
    """Verify mode propagation between SystemMode and Criticality."""
    assert is_hi_mode(SystemMode.HI) is True
    assert is_hi_mode(Criticality.HI) is True
    assert is_hi_mode(SystemMode.LO) is False

    assert is_lo_mode(SystemMode.LO) is True
    assert is_lo_mode(SystemMode.WARNING) is True
    assert is_lo_mode(Criticality.LO) is True
    assert is_lo_mode(SystemMode.HI) is False

    # Scheduler set_mode with SystemMode converts properly
    tasks = get_stress_20ms_workload()
    edf_vd = EDFVDScheduler(tasks=tasks)
    edf_vd.set_mode(SystemMode.HI)
    assert edf_vd.current_mode == Criticality.HI


def test_fix_9_runtime_monitor_state():
    """Verify runtime monitor calculates overrun_status only for actual overrunning HI jobs."""
    monitor = RuntimeMonitor()
    t_hi = Task(task_id=1, name="H1", criticality=Criticality.HI, period=20.0, relative_deadline=20.0, C_LO=2.0, C_HI=6.0)
    job = t_hi.generate_job(0, execution_budget=6.0)

    # Before C_LO
    job.execute(1.5)
    state = monitor.capture_job_state(job, current_time=1.5)
    assert state.overrun_status is False

    # At C_LO with required_execution > C_LO
    job.execute(0.5)
    state2 = monitor.capture_job_state(job, current_time=2.0)
    assert state2.overrun_status is True


def test_fix_10_risk_calculation():
    """Verify risk weights sum and evaluation logic."""
    estimator = RiskEstimator()
    assert pytest.approx(estimator.w_util + estimator.w_laxity + estimator.w_overrun + estimator.w_deadline) == 1.00
    r_total = estimator.calculate_total_risk(r_util=1.0, r_laxity=0.0, r_overrun=1.0, r_deadline=0.0)
    # 0.30 * 1.0 + 0.25 * 1.0 = 0.55
    assert pytest.approx(r_total, abs=1e-5) == 0.55


def test_fix_11_service_level_tracking_and_utility():
    """Verify utility calculation uses nominal requirement as denominator."""
    tasks = get_stress_20ms_workload()
    lo_tasks = [t for t in tasks if t.criticality == Criticality.LO]
    released = [t.generate_job(0) for t in lo_tasks]

    # Mutate required_execution (simulating degraded baseline execution)
    completed = []
    for j in released:
        j.required_execution = j.task.C_LO * 0.5
        j.executed_time = j.required_execution
        j.completed = True
        completed.append(j)

    deg_ctrl = DegradationController(tasks=tasks)
    metrics = deg_ctrl.calculate_utility_metrics(completed, released)

    # Total nominal utility is 130. Each task executed 50% -> achieved utility must be 65 (50%), not 100%!
    assert pytest.approx(metrics["LO_utility"], abs=1e-5) == 65.0
    assert pytest.approx(metrics["LO_utility_ratio"], abs=1e-5) == 0.50


def test_fix_12_hi_miss_ratio_metric():
    """Verify hi_miss_ratio is calculated strictly over HI released jobs."""
    tasks = get_stress_20ms_workload()
    config = SimulationConfig(duration=40.0)
    sim = Simulation(tasks=tasks, config=config, scenario=ExecutionScenario.NORMAL)
    summary = sim.run()

    assert "hi_released_jobs_count" in summary
    assert "hi_miss_ratio" in summary
    assert summary["hi_released_jobs_count"] == 4  # 2 HI tasks * 2 periods in 40ms
    assert summary["hi_miss_ratio"] == 0.0
