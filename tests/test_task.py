import pytest
from simulator.task import Task, Criticality


def test_task_creation_valid_hi():
    """Test successful creation of a valid HI-criticality task."""
    task = Task(
        task_id=1,
        name="Task_HI",
        criticality=Criticality.HI,
        period=10.0,
        relative_deadline=10.0,
        C_LO=2.0,
        C_HI=5.0,
        utility=1.0,
        minimum_service=0.5,
        maximum_service=1.0,
        release_offset=0.0,
    )
    assert task.task_id == 1
    assert task.name == "Task_HI"
    assert task.criticality == Criticality.HI
    assert task.period == 10.0
    assert task.relative_deadline == 10.0
    assert task.C_LO == 2.0
    assert task.C_HI == 5.0
    assert task.C_LO < task.C_HI


def test_task_creation_valid_lo():
    """Test successful creation of a valid LO-criticality task."""
    task = Task(
        task_id=2,
        name="Task_LO",
        criticality=Criticality.LO,
        period=20.0,
        relative_deadline=20.0,
        C_LO=4.0,
        C_HI=4.0,
        utility=0.8,
        minimum_service=0.0,
        maximum_service=1.0,
        release_offset=5.0,
    )
    assert task.task_id == 2
    assert task.criticality == Criticality.LO
    assert task.C_LO == task.C_HI == 4.0


def test_hi_task_clo_less_than_chi_validation():
    """Verify that HI tasks require C_LO < C_HI strictly."""
    # Valid HI task
    task = Task(
        task_id=1,
        name="Valid_HI",
        criticality=Criticality.HI,
        period=15.0,
        relative_deadline=15.0,
        C_LO=3.0,
        C_HI=6.0,
    )
    assert task.C_LO < task.C_HI

    # Invalid HI task: C_LO == C_HI
    with pytest.raises(ValueError, match="C_LO .* must be strictly less than C_HI"):
        Task(
            task_id=2,
            name="Invalid_HI_Equal",
            criticality=Criticality.HI,
            period=15.0,
            relative_deadline=15.0,
            C_LO=5.0,
            C_HI=5.0,
        )

    # Invalid HI task: C_LO > C_HI
    with pytest.raises(ValueError, match="C_LO .* must be strictly less than C_HI"):
        Task(
            task_id=3,
            name="Invalid_HI_Greater",
            criticality=Criticality.HI,
            period=15.0,
            relative_deadline=15.0,
            C_LO=7.0,
            C_HI=5.0,
        )


def test_lo_task_clo_equals_chi_validation():
    """Verify that LO tasks require C_LO == C_HI strictly."""
    # Valid LO task
    task = Task(
        task_id=1,
        name="Valid_LO",
        criticality=Criticality.LO,
        period=10.0,
        relative_deadline=10.0,
        C_LO=3.0,
        C_HI=3.0,
    )
    assert task.C_LO == task.C_HI

    # Invalid LO task: C_LO < C_HI
    with pytest.raises(ValueError, match="C_LO .* must equal C_HI"):
        Task(
            task_id=2,
            name="Invalid_LO_Less",
            criticality=Criticality.LO,
            period=10.0,
            relative_deadline=10.0,
            C_LO=2.0,
            C_HI=4.0,
        )

    # Invalid LO task: C_LO > C_HI
    with pytest.raises(ValueError, match="C_LO .* must equal C_HI"):
        Task(
            task_id=3,
            name="Invalid_LO_Greater",
            criticality=Criticality.LO,
            period=10.0,
            relative_deadline=10.0,
            C_LO=4.0,
            C_HI=2.0,
        )


def test_task_implicit_deadline_rule():
    """Verify primary experiment setting D_i = T_i."""
    task = Task(
        task_id=1,
        name="Implicit_Deadline_Task",
        criticality=Criticality.HI,
        period=25.0,
        relative_deadline=25.0,
        C_LO=5.0,
        C_HI=10.0,
    )
    assert task.relative_deadline == task.period
