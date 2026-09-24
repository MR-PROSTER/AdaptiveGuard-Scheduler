from typing import List, Optional, Dict, Any, Union
from simulator.task import Task
from simulator.job import Job
from simulator.event import Event, EventType
from simulator.event_queue import EventQueue
from simulator.cpu import CPU
from simulator.clock import SimulationClock
from config.default_config import SimulationConfig


class Simulation:
    """
    Discrete-Event Simulator for Mixed-Criticality Real-Time Systems.

    Attributes:
        tasks (List[Task]): Workload taskset.
        config (SimulationConfig): Simulation parameters.
        clock (SimulationClock): Simulation time clock (ms).
        event_queue (EventQueue): Priority queue for events.
        cpu (CPU): Single core CPU execution unit.
        active_jobs (List[Job]): Jobs currently released and active.
        ready_queue (List[Job]): Jobs ready for execution.
        completed_jobs (List[Job]): Jobs that completed execution.
        missed_jobs (List[Job]): Jobs that missed their deadline.
    """

    def __init__(
        self,
        tasks: List[Task],
        config: Optional[SimulationConfig] = None,
        scenario: Any = "NORMAL",
        seed: int = 42,
        overload_until_seq: int = 3,
    ) -> None:
        self.tasks: List[Task] = tasks
        self.config: SimulationConfig = config or SimulationConfig()
        from workloads.fixed_workload import ExecutionScenario
        if isinstance(scenario, str):
            scenario = ExecutionScenario(scenario)
        self.scenario: ExecutionScenario = scenario
        self.seed: int = seed
        self.overload_until_seq: int = overload_until_seq
        self.clock: SimulationClock = SimulationClock()
        self.event_queue: EventQueue = EventQueue()
        self.cpu: CPU = CPU(speed=self.config.cpu_speed)

        self.active_jobs: List[Job] = []
        self.ready_queue: List[Job] = []
        self.completed_jobs: List[Job] = []
        self.missed_jobs: List[Job] = []

        self.is_running: bool = False
        self.simulation_started: bool = False
        self.simulation_ended: bool = False
        self._scheduled_completion_events: Dict[str, Event] = {}

        self._initialize_simulation()

    @property
    def current_time(self) -> float:
        """Return current simulation time."""
        return self.clock.current_time

    def _initialize_simulation(self) -> None:
        """Pre-populate job releases and simulation end event."""
        # Schedule job release events up to simulation duration
        for task in self.tasks:
            k = 0
            while True:
                release_time = task.release_offset + k * task.period
                if release_time >= self.config.duration:
                    break
                
                # Push job release event
                release_event = Event(
                    time=release_time,
                    event_type=EventType.JOB_RELEASE,
                    task=task,
                    payload={"sequence_num": k},
                )
                self.event_queue.push(release_event)
                k += 1

        # Schedule simulation end event
        end_event = Event(
            time=self.config.duration,
            event_type=EventType.SIMULATION_END,
            priority=100,
        )
        self.event_queue.push(end_event)

    def _dispatch_next_job(self) -> None:
        """Dispatch highest priority (FIFO baseline) job from ready queue to CPU."""
        if self.cpu.is_idle() and self.ready_queue:
            job_to_run = self.ready_queue.pop(0)
            self.cpu.assign_job(job_to_run, self.current_time)

            # Schedule JOB_COMPLETION event
            exec_needed = job_to_run.remaining_execution / self.cpu.speed
            comp_time = self.current_time + exec_needed
            comp_event = Event(
                time=comp_time,
                event_type=EventType.JOB_COMPLETION,
                job=job_to_run,
            )
            self._scheduled_completion_events[job_to_run.job_id] = comp_event
            self.event_queue.push(comp_event)

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

            # End simulation if SIMULATION_END event reached
            if event.event_type == EventType.SIMULATION_END:
                # Advance remaining time slice to duration
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

            # Process event by type
            self._process_event(event)

            # Dispatch job if CPU is idle
            self._dispatch_next_job()

        self.is_running = False
        return self.get_summary()

    def _process_event(self, event: Event) -> None:
        """Handle individual event processing logic."""
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

            self.active_jobs.append(job)
            self.ready_queue.append(job)

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
                    # Finalize execution
                    self.cpu.execute(job.remaining_execution, self.current_time)

                job.completion_time = self.current_time
                job.completed = True

                if job in self.active_jobs:
                    self.active_jobs.remove(job)
                if job not in self.completed_jobs:
                    self.completed_jobs.append(job)

                self._scheduled_completion_events.pop(job.job_id, None)
                self.cpu.set_idle(self.current_time)

        elif event.event_type == EventType.DEADLINE:
            job = event.job
            if job and not job.completed:
                job.check_deadline(self.current_time)
                if job not in self.missed_jobs:
                    self.missed_jobs.append(job)

        elif event.event_type in (EventType.PREEMPTION, EventType.MONITOR, EventType.MODE_CHANGE):
            # Placeholder for future scheduler mechanics (EDF, EDF-VD, AdaptiveGuard)
            pass

    def get_summary(self) -> Dict[str, Any]:
        """Generate simulation statistics summary."""
        total_jobs = len(self.completed_jobs) + len(self.active_jobs)
        utilization = (
            (self.cpu.total_busy_time / self.config.duration)
            if self.config.duration > 0
            else 0.0
        )
        return {
            "duration": self.config.duration,
            "final_time": self.current_time,
            "total_jobs_released": total_jobs,
            "completed_jobs_count": len(self.completed_jobs),
            "missed_jobs_count": len(self.missed_jobs),
            "cpu_busy_time": self.cpu.total_busy_time,
            "cpu_utilization": utilization,
        }
