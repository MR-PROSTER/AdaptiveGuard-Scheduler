from typing import List, Optional, Dict, Any, Union, Tuple
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.event import Event, EventType
from simulator.event_queue import EventQueue
from simulator.cpu import CPU
from simulator.clock import SimulationClock
from config.default_config import SimulationConfig


class Simulation:
    """
    Discrete-Event Simulator for Mixed-Criticality Real-Time Systems.

    Supports scheduler selection, ready queue management, preemption, CPU execution,
    deadline miss detection, timeline generation, and comprehensive metric collection.
    """

    def __init__(
        self,
        tasks: List[Task],
        config: Optional[SimulationConfig] = None,
        scheduler: Any = None,
        scenario: Any = "NORMAL",
        seed: int = 42,
        overload_until_seq: int = 3,
    ) -> None:
        self.tasks: List[Task] = tasks
        self.config: SimulationConfig = config or SimulationConfig()

        if scheduler is None:
            from schedulers.edf import EDFScheduler
            scheduler = EDFScheduler()
        self.scheduler = scheduler

        from workloads.fixed_workload import ExecutionScenario
        if isinstance(scenario, str):
            scenario = ExecutionScenario(scenario)
        self.scenario: ExecutionScenario = scenario
        self.seed: int = seed
        self.overload_until_seq: int = overload_until_seq

        self.clock: SimulationClock = SimulationClock()
        self.event_queue: EventQueue = EventQueue()
        self.cpu: CPU = CPU(speed=self.config.cpu_speed)

        self.released_jobs: List[Job] = []
        self.active_jobs: List[Job] = []
        self.completed_jobs: List[Job] = []
        self.missed_jobs: List[Job] = []
        self.timeline: List[Tuple[float, str]] = []

        self.is_running: bool = False
        self.simulation_started: bool = False
        self.simulation_ended: bool = False
        self._scheduled_completion_events: Dict[str, Event] = {}

        self._initialize_simulation()

    def _check_mode_switch(self) -> None:
        """Check if current running HI job exceeded C_LO, triggering mode switch to HI mode."""
        current = self.cpu.current_job
        if (
            current
            and current.task.criticality == Criticality.HI
            and current.executed_time >= current.task.C_LO - 1e-9
            and current.required_execution > current.task.C_LO
        ):
            if hasattr(self.scheduler, "set_mode") and getattr(self.scheduler, "current_mode", None) == Criticality.LO:
                self.scheduler.set_mode(Criticality.HI)
                self._log_timeline(self.current_time, "MODE CHANGE: System switched to HI mode")

    @property
    def current_time(self) -> float:
        """Return current simulation time."""
        return self.clock.current_time

    def _get_task_short_name(self, task: Task) -> str:
        """Helper to return a short alias for task names if available."""
        alias_map = {
            "Flight_Control": "H1",
            "Braking_Control": "H2",
            "Telemetry": "L1",
            "Logging_A": "L2",
            "Logging_B": "L3",
            "Logging_C": "L4",
        }
        return alias_map.get(task.name, task.name)

    def _log_timeline(self, time: float, event_str: str) -> None:
        """Record timeline entry."""
        self.timeline.append((time, event_str))

    def _initialize_simulation(self) -> None:
        """Pre-populate job releases and simulation end event."""
        for task in self.tasks:
            k = 0
            while True:
                release_time = task.release_offset + k * task.period
                if release_time >= self.config.duration:
                    break
                
                release_event = Event(
                    time=release_time,
                    event_type=EventType.JOB_RELEASE,
                    task=task,
                    payload={"sequence_num": k},
                )
                self.event_queue.push(release_event)
                k += 1

        end_event = Event(
            time=self.config.duration,
            event_type=EventType.SIMULATION_END,
            priority=100,
        )
        self.event_queue.push(end_event)

    def _schedule_job_completion(self, job: Job) -> None:
        """Schedule a JOB_COMPLETION event for the currently running job."""
        exec_needed = job.remaining_execution / self.cpu.speed
        comp_time = self.current_time + exec_needed
        comp_event = Event(
            time=comp_time,
            event_type=EventType.JOB_COMPLETION,
            job=job,
        )
        self._scheduled_completion_events[job.job_id] = comp_event
        self.event_queue.push(comp_event)

    def _schedule_and_dispatch(self) -> None:
        """Evaluate scheduler decision and manage CPU assignment & preemption."""
        candidate_job = self.scheduler.select_job(self.current_time)
        current_job = self.cpu.current_job

        if candidate_job is None:
            return

        if current_job is None:
            # CPU is idle, assign candidate
            self.cpu.assign_job(candidate_job, self.current_time)
            self._schedule_job_completion(candidate_job)
        elif current_job != candidate_job:
            # Check preemption condition
            if self.scheduler.should_preempt(current_job, candidate_job):
                preempted = self.cpu.preempt(self.current_time)
                if preempted:
                    comp_event = self._scheduled_completion_events.pop(preempted.job_id, None)
                    if comp_event:
                        comp_event.cancelled = True
                    self.scheduler.add_job(preempted)
                    preempted_label = self._get_task_short_name(preempted.task)
                    candidate_label = self._get_task_short_name(candidate_job.task)
                    self._log_timeline(
                        self.current_time,
                        f"{preempted_label} preempted by {candidate_label}",
                    )

                self.cpu.assign_job(candidate_job, self.current_time)
                self._schedule_job_completion(candidate_job)

    def run(self) -> Dict[str, Any]:
        """
        Execute the discrete-event simulation.

        Returns:
            Dict[str, Any]: Summary dictionary of simulation results.
        """
        self.simulation_started = True
        self.is_running = True

        while not self.event_queue.is_empty() and self.is_running:
            event = self.event_queue.pop()
            if event.cancelled:
                continue

            # End simulation if SIMULATION_END event reached
            if event.event_type == EventType.SIMULATION_END:
                delta = event.time - self.current_time
                if delta > 0 and not self.cpu.is_idle():
                    self.cpu.execute(delta, self.current_time)
                self.clock.advance_to(event.time)
                self.simulation_ended = True
                break

            # Execute running job for elapsed time delta
            delta = event.time - self.current_time
            if delta > 0 and not self.cpu.is_idle():
                self.cpu.execute(delta, self.current_time)

            self.clock.advance_to(event.time)
            self._check_mode_switch()

            # Process event by type
            self._process_event(event)

            # Dispatch next job based on scheduler
            self._schedule_and_dispatch()

        self.is_running = False
        return self.get_summary()

    def _process_event(self, event: Event) -> None:
        """Handle individual event processing logic."""
        if event.cancelled:
            return

        if event.event_type == EventType.JOB_RELEASE:
            task = event.task
            seq_num = event.payload["sequence_num"] if event.payload else 0
            from workloads.fixed_workload import get_job_execution_requirement
            req_exec = get_job_execution_requirement(
                task=task,
                sequence_num=seq_num,
                scenario=self.scenario,
                seed=self.seed,
                overload_until_seq=self.overload_until_seq,
            )
            job = task.generate_job(seq_num, execution_budget=req_exec)

            self.released_jobs.append(job)
            self.active_jobs.append(job)
            task_label = self._get_task_short_name(job.task)
            self._log_timeline(self.current_time, f"{task_label} released")

            self.scheduler.on_job_release(job)

            # Schedule deadline event
            deadline_event = Event(
                time=job.absolute_deadline,
                event_type=EventType.DEADLINE,
                job=job,
                priority=10,
            )
            self.event_queue.push(deadline_event)

        elif event.event_type == EventType.JOB_COMPLETION:
            job = event.job
            if job and job == self.cpu.current_job:
                if not job.completed:
                    self.cpu.execute(job.remaining_execution, self.current_time)

                job.completion_time = self.current_time
                job.completed = True
                task_label = self._get_task_short_name(job.task)
                self._log_timeline(self.current_time, f"{task_label} completed")

                if job in self.active_jobs:
                    self.active_jobs.remove(job)
                if job not in self.completed_jobs:
                    self.completed_jobs.append(job)

                self.scheduler.on_job_completion(job)
                self._scheduled_completion_events.pop(job.job_id, None)
                self.cpu.set_idle(self.current_time)

        elif event.event_type == EventType.DEADLINE:
            job = event.job
            if job and not job.completed:
                job.check_deadline(self.current_time)
                if job not in self.missed_jobs:
                    self.missed_jobs.append(job)
                    task_label = self._get_task_short_name(job.task)
                    self._log_timeline(self.current_time, f"{task_label} missed deadline")

        elif event.event_type in (EventType.PREEMPTION, EventType.MONITOR, EventType.MODE_CHANGE):
            pass

    def get_summary(self) -> Dict[str, Any]:
        """Generate simulation statistics summary."""
        total_released = len(self.released_jobs)
        total_completed = len(self.completed_jobs)
        total_missed = len(self.missed_jobs)

        response_times = [
            j.completion_time - j.release_time
            for j in self.completed_jobs
            if j.completion_time is not None
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )

        utilization = (
            (self.cpu.total_busy_time / self.config.duration)
            if self.config.duration > 0
            else 0.0
        )
        return {
            "scheduler": self.scheduler.name,
            "duration": self.config.duration,
            "final_time": self.current_time,
            "total_jobs_released": total_released,
            "completed_jobs_count": total_completed,
            "missed_jobs_count": total_missed,
            "average_response_time": avg_response_time,
            "cpu_busy_time": self.cpu.total_busy_time,
            "cpu_utilization": utilization,
            "timeline": self.timeline,
        }
