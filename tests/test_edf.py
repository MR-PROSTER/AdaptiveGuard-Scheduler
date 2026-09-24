import pytest
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.simulation import Simulation
from config.default_config import SimulationConfig
from schedulers.edf import EDFScheduler
from workloads.fixed_workload import get_stress_20ms_workload, ExecutionScenario


def test_edf_priority_tie_breaking_rules():
    """
    Verify the 4 priority tie-breaking rules of EDF Scheduler:
      1. smallest absolute deadline
      2. HI criticality first
      3. earlier release time
      4. smaller task ID
    """
    scheduler = EDFScheduler()

    # Base tasks
    t1_hi = Task(task_id=1, name="H1", criticality=Criticality.HI, period=20.0, relative_deadline=20.0, C_LO=2.0, C_HI=6.0)
    t2_hi = Task(task_id=2, name="H2", criticality=Criticality.HI, period=20.0, relative_deadline=20.0, C_LO=3.0, C_HI=7.0)
    t3_lo = Task(task_id=3, name="L1", criticality=Criticality.LO, period=20.0, relative_deadline=20.0, C_LO=6.0, C_HI=6.0)

    # Rule 1: Smallest absolute deadline
    j_earlier_deadline = Job(job_id="T3_J0", task=t3_lo, release_time=0.0, absolute_deadline=15.0, required_execution=6.0, remaining_execution=6.0)
    j_later_deadline = Job(job_id="T1_J0", task=t1_hi, release_time=0.0, absolute_deadline=20.0, required_execution=2.0, remaining_execution=2.0)

    scheduler.add_job(j_later_deadline)
    scheduler.add_job(j_earlier_deadline)
    assert scheduler.select_job(0.0) == j_earlier_deadline
    assert scheduler.should_preempt(j_later_deadline, j_earlier_deadline) is True
    assert scheduler.should_preempt(j_earlier_deadline, j_later_deadline) is False

    scheduler.ready_queue.clear()

    # Rule 2: Equal deadline -> HI criticality first
    j_hi_deadline_20 = Job(job_id="T1_J0", task=t1_hi, release_time=0.0, absolute_deadline=20.0, required_execution=2.0, remaining_execution=2.0)
    j_lo_deadline_20 = Job(job_id="T3_J0", task=t3_lo, release_time=0.0, absolute_deadline=20.0, required_execution=6.0, remaining_execution=6.0)

    scheduler.add_job(j_lo_deadline_20)
    scheduler.add_job(j_hi_deadline_20)
    assert scheduler.select_job(0.0) == j_hi_deadline_20
    assert scheduler.should_preempt(j_lo_deadline_20, j_hi_deadline_20) is True

    scheduler.ready_queue.clear()

    # Rule 3: Equal deadline and criticality -> earlier release time
    j_release_0 = Job(job_id="T1_J0", task=t1_hi, release_time=0.0, absolute_deadline=20.0, required_execution=2.0, remaining_execution=2.0)
    j_release_5 = Job(job_id="T2_J0", task=t2_hi, release_time=5.0, absolute_deadline=20.0, required_execution=3.0, remaining_execution=3.0)

    scheduler.add_job(j_release_5)
    scheduler.add_job(j_release_0)
    assert scheduler.select_job(5.0) == j_release_0

    scheduler.ready_queue.clear()

    # Rule 4: Equal deadline, criticality, and release time -> smaller task ID
    j_task1 = Job(job_id="T1_J0", task=t1_hi, release_time=0.0, absolute_deadline=20.0, required_execution=2.0, remaining_execution=2.0)
    j_task2 = Job(job_id="T2_J0", task=t2_hi, release_time=0.0, absolute_deadline=20.0, required_execution=3.0, remaining_execution=3.0)

    scheduler.add_job(j_task2)
    scheduler.add_job(j_task1)
    assert scheduler.select_job(0.0) == j_task1


def test_edf_preemption_execution():
    """Verify preemption occurs when a job with an earlier deadline releases while CPU is busy."""
    scheduler = EDFScheduler()
    t_long = Task(task_id=10, name="LongTask", criticality=Criticality.LO, period=100.0, relative_deadline=100.0, C_LO=20.0, C_HI=20.0)
    t_urgent = Task(task_id=20, name="UrgentTask", criticality=Criticality.HI, period=20.0, relative_deadline=10.0, C_LO=4.0, C_HI=8.0, release_offset=5.0)

    config = SimulationConfig(duration=50.0, verbose=False)
    sim = Simulation(tasks=[t_long, t_urgent], config=config, scheduler=scheduler)
    summary = sim.run()

    # Find timeline events
    timeline = summary["timeline"]
    events_at_5 = [e for t, e in timeline if t == 5.0]
    
    # UrgentTask released at 5.0 and preempts LongTask
    assert any("UrgentTask released" in e for e in events_at_5)
    assert any("LongTask preempted by UrgentTask" in e for e in events_at_5)

    # UrgentTask completes at 5.0 + 4.0 = 9.0
    events_at_9 = [e for t, e in timeline if t == 9.0]
    assert any("UrgentTask completed" in e for e in events_at_9)


def test_edf_overload_behavior():
    """Verify EDF behavior under BOTH_OVERRUN scenario (total utilization 1.10)."""
    tasks = get_stress_20ms_workload()
    config = SimulationConfig(duration=40.0, verbose=False)
    sim = Simulation(tasks=tasks, config=config, scenario=ExecutionScenario.BOTH_OVERRUN)

    summary = sim.run()

    # Under 1.10 worst-case utilization, deadline misses must occur
    assert summary["missed_jobs_count"] > 0
    # Response time metric calculated
    assert summary["average_response_time"] > 0.0


def test_edf_metrics_summary():
    """Verify accuracy of returned metrics in summary."""
    tasks = get_stress_20ms_workload()
    config = SimulationConfig(duration=100.0, verbose=False)
    sim = Simulation(tasks=tasks, config=config, scenario=ExecutionScenario.NORMAL)

    summary = sim.run()

    assert summary["scheduler"] == "EDF"
    assert summary["total_jobs_released"] == 30
    assert summary["completed_jobs_count"] == 30
    assert summary["missed_jobs_count"] == 0
    assert pytest.approx(summary["cpu_utilization"], abs=1e-5) == 0.70
    assert summary["average_response_time"] > 0.0
