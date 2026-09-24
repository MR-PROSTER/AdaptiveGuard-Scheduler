import pytest
from simulator.task import Task, Criticality
from simulator.job import Job


def test_job_release_time_calculation():
    """Verify job release time formula: release_time = offset + k * period."""
    task = Task(
        task_id=10,
        name="Periodic_Task",
        criticality=Criticality.HI,
        period=15.0,
        relative_deadline=15.0,
        C_LO=3.0,
        C_HI=6.0,
        release_offset=5.0,
    )

    # Job k=0: release_time = 5.0 + 0 * 15.0 = 5.0
    job_0 = task.generate_job(sequence_num=0)
    assert job_0.release_time == 5.0

    # Job k=1: release_time = 5.0 + 1 * 15.0 = 20.0
    job_1 = task.generate_job(sequence_num=1)
    assert job_1.release_time == 20.0

    # Job k=4: release_time = 5.0 + 4 * 15.0 = 65.0
    job_4 = task.generate_job(sequence_num=4)
    assert job_4.release_time == 65.0


def test_job_absolute_deadline_calculation():
    """Verify job absolute deadline formula: absolute_deadline = release_time + relative_deadline."""
    task = Task(
        task_id=20,
        name="Deadline_Task",
        criticality=Criticality.LO,
        period=20.0,
        relative_deadline=20.0,
        C_LO=4.0,
        C_HI=4.0,
        release_offset=10.0,
    )

    # Job k=0: release = 10.0, abs_deadline = 10.0 + 20.0 = 30.0
    job_0 = task.generate_job(sequence_num=0)
    assert job_0.release_time == 10.0
    assert job_0.absolute_deadline == 30.0

    # Job k=2: release = 10.0 + 2 * 20.0 = 50.0, abs_deadline = 50.0 + 20.0 = 70.0
    job_2 = task.generate_job(sequence_num=2)
    assert job_2.release_time == 50.0
    assert job_2.absolute_deadline == 70.0


def test_job_remaining_execution_updates():
    """Verify remaining_execution, executed_time, and completed flags update correctly when executed."""
    task = Task(
        task_id=30,
        name="Execution_Task",
        criticality=Criticality.HI,
        period=30.0,
        relative_deadline=30.0,
        C_LO=5.0,
        C_HI=10.0,
        release_offset=0.0,
    )

    job = task.generate_job(sequence_num=0, execution_budget=5.0)

    assert job.required_execution == 5.0
    assert job.remaining_execution == 5.0
    assert job.executed_time == 0.0
    assert not job.completed

    # Execute partial duration = 2.0 ms
    actual_1 = job.execute(2.0)
    assert actual_1 == 2.0
    assert job.executed_time == 2.0
    assert job.remaining_execution == 3.0
    assert not job.completed

    # Execute remaining duration = 3.0 ms
    actual_2 = job.execute(3.0)
    assert actual_2 == 3.0
    assert job.executed_time == 5.0
    assert job.remaining_execution == 0.0
    assert job.completed

    # Attempt further execution on completed job -> returns 0.0
    actual_3 = job.execute(2.0)
    assert actual_3 == 0.0
    assert job.executed_time == 5.0
    assert job.remaining_execution == 0.0


def test_job_deadline_miss_checking():
    """Verify job deadline miss flag detection."""
    task = Task(
        task_id=40,
        name="Missed_Deadline_Task",
        criticality=Criticality.LO,
        period=10.0,
        relative_deadline=10.0,
        C_LO=2.0,
        C_HI=2.0,
        release_offset=0.0,
    )

    job = task.generate_job(sequence_num=0) # release = 0.0, deadline = 10.0

    # Before deadline -> no miss
    assert not job.check_deadline(current_time=8.0)
    assert not job.missed_deadline

    # Exactly at deadline -> no miss
    assert not job.check_deadline(current_time=10.0)
    assert not job.missed_deadline

    # Past deadline without completion -> deadline miss!
    assert job.check_deadline(current_time=10.1)
    assert job.missed_deadline
