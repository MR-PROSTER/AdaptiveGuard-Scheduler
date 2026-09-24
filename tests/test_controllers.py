import pytest
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.simulation import Simulation
from config.default_config import SimulationConfig
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from controllers.runtime_monitor import RuntimeMonitor, JobState
from controllers.risk_estimator import RiskEstimator, RiskMetrics, clamp


def test_important_risk_combination_test():
    """
    REQUIRED IMPORTANT TEST FROM PROMPT:
      R_util = 0.72
      R_laxity = 0.83
      R_overrun = 1.0
      R_deadline = 0.60

    Expected:
      R_total = 0.805
    """
    estimator = RiskEstimator(
        w_util=0.30,
        w_laxity=0.30,
        w_overrun=0.25,
        w_deadline=0.15,
    )
    r_util = 0.72
    r_laxity = 0.83
    r_overrun = 1.0
    r_deadline = 0.60

    r_total = estimator.calculate_total_risk(r_util, r_laxity, r_overrun, r_deadline)
    assert pytest.approx(r_total, abs=1e-6) == 0.805


def test_laxity_and_job_state_calculation():
    """Verify laxity calculation: L_i(t) = D_i - t - R_i(t)."""
    task = Task(
        task_id=1,
        name="Flight_Control",
        criticality=Criticality.HI,
        period=20.0,
        relative_deadline=20.0,
        C_LO=2.0,
        C_HI=6.0,
    )
    job = Job(
        job_id="T1_J0",
        task=task,
        release_time=0.0,
        absolute_deadline=20.0,
        required_execution=6.0,
        remaining_execution=4.0,  # 2ms executed
    )
    job.executed_time = 2.0

    monitor = RuntimeMonitor()
    state = monitor.capture_job_state(job, current_time=2.0)

    assert state.execution_received == 2.0
    assert state.remaining_execution == 4.0
    assert state.absolute_deadline == 20.0
    assert state.time_to_deadline == 18.0
    # Laxity = 20.0 - 2.0 - 4.0 = 14.0 ms
    assert state.laxity == 14.0
    assert state.overrun_status is True  # executed >= C_LO (2.0) and incomplete


def test_laxity_risk_piecewise_formula():
    """Verify R_laxity rules for L_safe = 5ms."""
    estimator = RiskEstimator(l_safe=5.0)

    hi_task = Task(task_id=1, name="H1", criticality=Criticality.HI, period=20.0, relative_deadline=20.0, C_LO=2.0, C_HI=6.0)

    # 1. L_min >= 5 -> R_laxity = 0
    js_safe = JobState("J1", 1, "H1", Criticality.HI, 0, 4, 20, 20, 10.0, 2, 6, False)
    assert estimator.calculate_r_laxity([js_safe]) == 0.0

    # 2. L_min <= 0 -> R_laxity = 1
    js_neg = JobState("J1", 1, "H1", Criticality.HI, 0, 10, 20, 5, -5.0, 2, 6, False)
    assert estimator.calculate_r_laxity([js_neg]) == 1.0

    # 3. 0 < L_min < 5 -> R_laxity = 1 - L_min/5
    # L_min = 2.0 -> 1 - 2/5 = 0.6
    js_mid = JobState("J1", 1, "H1", Criticality.HI, 0, 8, 20, 10, 2.0, 2, 6, False)
    assert pytest.approx(estimator.calculate_r_laxity([js_mid]), abs=1e-6) == 0.6


def test_deadline_risk_piecewise_formula():
    """Verify R_deadline rules for T_safe = 5ms."""
    estimator = RiskEstimator(t_safe=5.0)

    # 1. time_to_deadline >= 5 -> R_deadline = 0
    js_safe = JobState("J1", 1, "H1", Criticality.HI, 0, 2, 20, 15.0, 13, 2, 6, False)
    assert estimator.calculate_r_deadline([js_safe]) == 0.0

    # 2. time_to_deadline <= 0 -> R_deadline = 1
    js_passed = JobState("J1", 1, "H1", Criticality.HI, 0, 2, 20, 0.0, -2, 2, 6, False)
    assert estimator.calculate_r_deadline([js_passed]) == 1.0

    # 3. 0 < time_to_deadline < 5 -> R_deadline = 1 - time_to_deadline/5
    # time_to_deadline = 2.0 -> 1 - 2/5 = 0.6
    js_mid = JobState("J1", 1, "H1", Criticality.HI, 0, 2, 20, 2.0, 0, 2, 6, False)
    assert pytest.approx(estimator.calculate_r_deadline([js_mid]), abs=1e-6) == 0.6


def test_overrun_risk_logic():
    """Verify R_overrun is 1.0 if any active HI job reaches C_LO without completion."""
    estimator = RiskEstimator()

    # HI job not reached C_LO -> 0
    js_no_overrun = JobState("J1", 1, "H1", Criticality.HI, 1.0, 1.0, 20, 19, 18, 2.0, 6.0, False)
    assert estimator.calculate_r_overrun([js_no_overrun]) == 0.0

    # HI job reached C_LO -> 1
    js_overrun = JobState("J1", 1, "H1", Criticality.HI, 2.0, 4.0, 20, 18, 14, 2.0, 6.0, True)
    assert estimator.calculate_r_overrun([js_overrun]) == 1.0


def test_monitoring_checkpoints_simulation():
    """Verify simulation records risk snapshots at discrete checkpoints."""
    tasks = get_stress_20ms_workload()
    config = SimulationConfig(duration=10.0, verbose=False)
    sim = Simulation(tasks=tasks, config=config, scenario=ExecutionScenario.NORMAL, monitor_interval=0.5)

    summary = sim.run()
    risk_history = summary["risk_history"]

    assert len(risk_history) > 0
    # Check discrete timestamps exist at multiples of 0.5ms
    timestamps = [rm.timestamp for rm in risk_history]
    assert 0.0 in timestamps
    assert 0.5 in timestamps
    assert 1.0 in timestamps
