import pytest
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.simulation import Simulation
from config.default_config import SimulationConfig
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario
from schedulers.edf import EDFScheduler
from schedulers.edf_vd import (
    EDFVDScheduler,
    calculate_x,
    virtual_deadline,
)


def test_calculate_x_fixed_workload():
    """
    Test 1: Verify x for the fixed workload is approximately 0.454545 (5/11).
    Formula: x = U_HI_LO / (1 - U_LO)
      U_HI_LO = 2/20 + 3/20 = 0.25
      U_LO = (6+1+1+1)/20 = 0.45
      x = 0.25 / 0.55 = 5/11 = 0.4545454545...
    """
    tasks = get_stress_20ms_workload()
    x = calculate_x(tasks)
    expected_x = 0.25 / 0.55  # 5/11
    assert pytest.approx(x, abs=1e-5) == 0.454545
    assert pytest.approx(x, abs=1e-9) == expected_x


def test_virtual_deadline_hi_task_in_lo_mode():
    """
    Test 2: Verify Virtual deadline is calculated correctly for HI task in LO mode.
    d'_i = release_time + x * (absolute_deadline - release_time)
    """
    hi_task = Task(
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
        task=hi_task,
        release_time=0.0,
        absolute_deadline=20.0,
        required_execution=2.0,
        remaining_execution=2.0,
    )
    x = 5.0 / 11.0  # 0.454545...

    vd = virtual_deadline(job, x, current_mode=Criticality.LO)
    # 0.0 + (5/11) * (20.0 - 0.0) = 100/11 = 9.090909...
    assert pytest.approx(vd, abs=1e-5) == 9.09091
    assert pytest.approx(vd, abs=1e-9) == 100.0 / 11.0

    # Test with offset release_time
    job_offset = Job(
        job_id="T1_J1",
        task=hi_task,
        release_time=20.0,
        absolute_deadline=40.0,
        required_execution=2.0,
        remaining_execution=2.0,
    )
    vd_offset = virtual_deadline(job_offset, x, current_mode=Criticality.LO)
    # 20.0 + (5/11) * 20.0 = 20.0 + 9.090909 = 29.090909...
    assert pytest.approx(vd_offset, abs=1e-5) == 29.09091


def test_virtual_deadline_lo_task_unchanged():
    """
    Test 3: Verify LO task deadline is unchanged in LO mode.
    """
    lo_task = Task(
        task_id=3,
        name="Telemetry",
        criticality=Criticality.LO,
        period=20.0,
        relative_deadline=20.0,
        C_LO=6.0,
        C_HI=6.0,
    )
    job = Job(
        job_id="T3_J0",
        task=lo_task,
        release_time=0.0,
        absolute_deadline=20.0,
        required_execution=6.0,
        remaining_execution=6.0,
    )
    x = 5.0 / 11.0

    vd = virtual_deadline(job, x, current_mode=Criticality.LO)
    assert vd == 20.0


def test_virtual_deadline_hi_task_in_hi_mode():
    """
    Test 4: Verify HI task switches back to actual deadline in HI mode.
    """
    hi_task = Task(
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
        task=hi_task,
        release_time=0.0,
        absolute_deadline=20.0,
        required_execution=6.0,
        remaining_execution=6.0,
    )
    x = 5.0 / 11.0

    vd_hi_mode = virtual_deadline(job, x, current_mode=Criticality.HI)
    assert vd_hi_mode == 20.0


def test_edf_vd_scheduler_mode_switch():
    """Verify EDFVDScheduler mode transition and ready queue filtering."""
    tasks = get_stress_20ms_workload()
    scheduler = EDFVDScheduler(tasks=tasks)
    assert pytest.approx(scheduler.x, abs=1e-5) == 0.454545
    assert scheduler.current_mode == Criticality.LO

    hi_task = tasks[0]
    lo_task = tasks[2]

    j1 = hi_task.generate_job(0)
    j2 = lo_task.generate_job(0)

    scheduler.add_job(j1)
    scheduler.add_job(j2)
    assert len(scheduler.ready_queue) == 2

    # Transition to HI mode
    scheduler.set_mode(Criticality.HI)
    assert scheduler.current_mode == Criticality.HI
    # LO job should be dropped from ready queue upon mode switch
    assert len(scheduler.ready_queue) == 1
    assert scheduler.ready_queue[0] == j1
