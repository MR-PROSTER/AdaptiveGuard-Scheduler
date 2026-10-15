from typing import List, Optional, Dict, Any, Union, Tuple
from simulator.task import Task, Criticality
from simulator.job import Job
from simulator.event import Event, EventType
from simulator.event_queue import EventQueue
from simulator.cpu import CPU
from simulator.clock import SimulationClock
from config.default_config import SimulationConfig


from controllers.runtime_monitor import RuntimeMonitor
from controllers.risk_estimator import RiskEstimator, RiskMetrics
from controllers.mode_controller import AdaptiveGuardModeController, SystemMode
from controllers.degradation_controller import DegradationController
from controllers.recovery_controller import GradualRecoveryController


class Simulation:
    """
    Discrete-Event Simulator for Mixed-Criticality Real-Time Systems.

    Supports scheduler selection, ready queue management, preemption, CPU execution,
    deadline miss detection, timeline generation, runtime monitoring, and risk estimation.
    """

    def __init__(
        self,
        tasks: List[Task],
        config: Optional[SimulationConfig] = None,
        scheduler: Any = None,
        scenario: Any = "NORMAL",
        seed: int = 42,
        overload_until_seq: int = 3,
        monitor_interval: float = 0.5,
        enable_monitoring: bool = True,
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

        self.monitor_interval: float = monitor_interval
        self.enable_monitoring: bool = enable_monitoring

        from schedulers.adaptive_guard import AdaptiveGuardScheduler
        if isinstance(self.scheduler, AdaptiveGuardScheduler):
            self.monitor = self.scheduler.runtime_monitor
            self.risk_estimator = self.scheduler.risk_estimator
            self.mode_controller = self.scheduler.mode_controller
            self.degradation_controller = self.scheduler.degradation_controller
        else:
            self.monitor = RuntimeMonitor(monitor_interval=self.monitor_interval)
            self.risk_estimator = RiskEstimator()
            self.mode_controller = AdaptiveGuardModeController()
            self.degradation_controller = DegradationController(self.tasks)

        # Wire ablation config if present
        ablation_config = getattr(self.scheduler, "ablation_config", None)
        if ablation_config is not None:
            if not ablation_config.enable_risk:
                self.enable_monitoring = False
            self.degradation_controller.ablation_config = ablation_config
            self.mode_controller.ablation_config = ablation_config

        self.recovery_controller = GradualRecoveryController(self.tasks, self.degradation_controller)
        self.risk_history: List[RiskMetrics] = []
        self.scheduling_decisions: List[Dict[str, Any]] = []

        if hasattr(self.scheduler, "degradation_controller"):
            self.scheduler.degradation_controller = self.degradation_controller

        # Computational Overhead Tracking
        self.scheduler_invocations: int = 0
        self.risk_calculations: int = 0
        self.mode_transitions: int = 0
        self.scheduler_decision_count: int = 0
        self.risk_calculation_count: int = 0
        self.mode_transition_count: int = 0

        self.clock: SimulationClock = SimulationClock()
        self.event_queue: EventQueue = EventQueue()
        self.cpu: CPU = CPU(speed=self.config.cpu_speed)

        self.released_jobs: List[Job] = []
        self.active_jobs: List[Job] = []
        self.completed_jobs: List[Job] = []
        self.missed_jobs: List[Job] = []
        self.timeline: List[Tuple[float, str]] = []
        self.state_timeline: List[Dict[str, Any]] = []

        # Mode Durations and Recovery Tracking
        self.mode_durations: Dict[str, float] = {"LO": 0.0, "WARNING": 0.0, "HI": 0.0, "RECOVERY": 0.0}
        self.last_mode_change_time: float = 0.0
        self.current_system_mode_name: str = "LO"
        self.recovery_episodes: List[float] = []
        self.recovery_entry_time: Optional[float] = None

        self.is_running: bool = False
        self.simulation_started: bool = False
        self.simulation_ended: bool = False
        self._scheduled_completion_events: Dict[str, Event] = {}
        self._scheduled_overrun_events: Dict[str, Event] = {}

        self._initialize_simulation()

    def _trigger_risk_evaluation(self, trigger_name: str) -> None:
        """Capture active job state, evaluate risk components, and update mode & degradation controllers."""
        if not self.enable_monitoring:
            return
        self.risk_calculations += 1
        self.risk_calculation_count = self.risk_calculations
        if self.config.enable_overhead:
            self.cpu.total_busy_time += self.config.risk_estimation_overhead

        job_states = self.monitor.monitor_active_jobs(self.active_jobs, self.current_time)
        risk_snapshot = self.risk_estimator.evaluate(
            job_states, self.current_time, self.cpu.speed, event_trigger=trigger_name
        )
        self.risk_history.append(risk_snapshot)

        # Check if recovery is complete if currently recovering
        rec_complete = False
        if self.mode_controller.current_mode == SystemMode.RECOVERY:
            rec_complete = all(
                self.degradation_controller.get_service_level(t.task_id) >= 1.00
                for t in self.tasks
                if t.criticality == Criticality.LO
            )

        # Update Mode Controller with evaluated risk
        old_mode = self.mode_controller.current_mode
        new_mode = self.mode_controller.update(
            self.current_time,
            risk_snapshot.r_total,
            recovery_completed=rec_complete,
            r_util=risk_snapshot.r_util,
            r_laxity=risk_snapshot.r_laxity,
            r_overrun=risk_snapshot.r_overrun,
            r_deadline=risk_snapshot.r_deadline,
        )
        self._log_timeline(
            self.current_time,
            f"RISK EVAL: R_total={risk_snapshot.r_total:.4f} (util={risk_snapshot.r_util:.2f}, lax={risk_snapshot.r_laxity:.2f}, ovr={risk_snapshot.r_overrun:.2f}, ddl={risk_snapshot.r_deadline:.2f}, Trigger: {trigger_name})",
        )

        if old_mode != new_mode:
            self.mode_transitions += 1
            self.mode_transition_count = self.mode_transitions
            new_mode_str = getattr(new_mode, "value", str(new_mode)).upper()
            self._record_mode_transition_duration(self.current_time, new_mode_str)
            if self.config.enable_overhead:
                self.cpu.total_busy_time += self.config.mode_transition_overhead
            if hasattr(self.scheduler, "set_mode"):
                self.scheduler.set_mode(new_mode)

            if self.mode_controller.transitions:
                last_trans = self.mode_controller.transitions[-1]
                self._log_timeline(
                    self.current_time,
                    f"MODE TRANSITION: {last_trans.old_mode.value} -> {last_trans.new_mode.value} (Risk={last_trans.risk:.4f}, R_util={last_trans.r_util:.2f}, R_laxity={last_trans.r_laxity:.2f}, R_overrun={last_trans.r_overrun:.2f}, R_deadline={last_trans.r_deadline:.2f}, Reason: {last_trans.reason})",
                )

        # Update LO task service levels via Degradation and Recovery Controllers
        old_change_count = len(self.degradation_controller.service_change_log)
        if new_mode == SystemMode.RECOVERY:
            self.recovery_controller.update_recovery(
                self.current_time, new_mode, risk_snapshot.r_total
            )
        else:
            self.degradation_controller.update(
                self.current_time, new_mode, risk_snapshot.r_total
            )

        # Propagate service level degradation to active LO jobs in real time
        self._propagate_degradation_to_active_jobs()

        # Log new service changes to timeline
        new_changes = self.degradation_controller.service_change_log[old_change_count:]
        for change in new_changes:
            self._log_timeline(
                self.current_time,
                f"SERVICE CHANGE: Task {change.task_name} service {change.old_service:.2f} -> {change.new_service:.2f} (Density={change.utility_density:.4f}, Reason: {change.reason})",
            )

        # Record system state snapshot (time | running job | risk | mode | service levels)
        service_map = {
            self._get_task_short_name(t): self.degradation_controller.get_service_level(t.task_id)
            for t in self.tasks
            if t.criticality == Criticality.LO
        }
        current_job_str = (
            self._get_task_short_name(self.cpu.current_job.task)
            if (self.cpu.current_job and not self.cpu.is_idle())
            else "IDLE"
        )
        self.state_timeline.append(
            {
                "time": self.current_time,
                "running_job": current_job_str,
                "risk": risk_snapshot.r_total,
                "mode": getattr(
                    self.mode_controller.current_mode,
                    "value",
                    str(self.mode_controller.current_mode),
                ),
                "service_levels": service_map,
                "r_util": risk_snapshot.r_util,
                "r_laxity": risk_snapshot.r_laxity,
                "r_overrun": risk_snapshot.r_overrun,
                "r_deadline": risk_snapshot.r_deadline,
                "trigger": trigger_name,
            }
        )

    def _propagate_degradation_to_active_jobs(self) -> None:
        """Propagate updated service levels to active LO jobs in real time."""
        for job in list(self.active_jobs):
            if job.task.criticality == Criticality.LO and not job.completed:
                s = self.degradation_controller.get_service_level(job.task.task_id)
                target_budget = job.task.C_LO * s
                if job.executed_time >= target_budget - 1e-9:
                    job.remaining_execution = 0.0
                    job.completed = True
                    if job in self.active_jobs:
                        self.active_jobs.remove(job)
                    if job not in self.completed_jobs:
                        self.completed_jobs.append(job)
                    if job == self.cpu.current_job:
                        self.cpu.set_idle(self.current_time)
                        comp_ev = self._scheduled_completion_events.pop(job.job_id, None)
                        if comp_ev:
                            comp_ev.cancelled = True
                    self.scheduler.on_job_completion(job)
                else:
                    new_remaining = target_budget - job.executed_time
                    if abs(new_remaining - job.remaining_execution) > 1e-6:
                        job.remaining_execution = new_remaining
                        if job == self.cpu.current_job:
                            comp_ev = self._scheduled_completion_events.pop(job.job_id, None)
                            if comp_ev:
                                comp_ev.cancelled = True
                            self._schedule_job_completion(job)

    def _check_mode_switch(self) -> None:
        """Check if current running HI job exceeded C_LO, triggering mode switch or task escalation."""
        current = self.cpu.current_job
        if (
            current
            and current.task.criticality == Criticality.HI
            and current.executed_time >= current.task.C_LO - 1e-9
            and current.required_execution > current.task.C_LO
        ):
            from controllers.mode_controller import is_lo_mode
            task_label = self._get_task_short_name(current.task)

            if hasattr(self.scheduler, "on_task_overrun"):
                if not getattr(self.scheduler, "is_task_escalated", lambda t: False)(current.task):
                    self.scheduler.on_task_overrun(current.task)
                    self.mode_transitions += 1
                    self.mode_transition_count = self.mode_transitions
                    if self.config.enable_overhead:
                        self.cpu.total_busy_time += self.config.mode_transition_overhead
                    self._log_timeline(self.current_time, f"ESCALATION: {task_label} escalated to HI behavior")
                    self._trigger_risk_evaluation(f"HI Task Overrun ({task_label} reached C_LO)")
            elif self.enable_monitoring:
                self._trigger_risk_evaluation(f"HI Task Overrun ({task_label} reached C_LO)")
            elif hasattr(self.scheduler, "set_mode") and is_lo_mode(getattr(self.scheduler, "current_mode", None)):
                old_change_count = len(self.degradation_controller.service_change_log)
                try:
                    self.scheduler.set_mode(Criticality.HI, current_time=self.current_time)
                except TypeError:
                    self.scheduler.set_mode(Criticality.HI)
                self.mode_transitions += 1
                self.mode_transition_count = self.mode_transitions
                if self.config.enable_overhead:
                    self.cpu.total_busy_time += self.config.mode_transition_overhead
                self._log_timeline(self.current_time, "MODE CHANGE: System switched to HI mode")
                self.mode_controller.current_mode = SystemMode.HI
                self._record_mode_transition_duration(self.current_time, "HI")
                self.degradation_controller.update(self.current_time, SystemMode.HI, 1.0)
                self._propagate_degradation_to_active_jobs()
                new_changes = self.degradation_controller.service_change_log[old_change_count:]
                for change in new_changes:
                    self._log_timeline(
                        self.current_time,
                        f"SERVICE CHANGE: Task {change.task_name} service {change.old_service:.2f} -> {change.new_service:.2f} (Density={change.utility_density:.4f}, Reason: {change.reason})",
                    )

    def _record_mode_transition_duration(self, current_time: float, new_mode_str: str) -> None:
        """Update cumulative mode durations and track recovery episode durations."""
        elapsed = current_time - self.last_mode_change_time
        if elapsed > 0:
            cur = self.current_system_mode_name
            self.mode_durations[cur] = self.mode_durations.get(cur, 0.0) + elapsed

        # Check recovery episode start/stop
        if new_mode_str == "RECOVERY" and self.recovery_entry_time is None:
            self.recovery_entry_time = current_time
        elif self.current_system_mode_name == "RECOVERY" and new_mode_str != "RECOVERY":
            if self.recovery_entry_time is not None:
                self.recovery_episodes.append(current_time - self.recovery_entry_time)
                self.recovery_entry_time = None

        self.last_mode_change_time = current_time
        self.current_system_mode_name = new_mode_str

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
        """Pre-populate job releases, periodic monitoring, and simulation end event."""
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

        if self.enable_monitoring and self.monitor_interval > 0:
            t = 0.0
            while t < self.config.duration:
                mon_event = Event(
                    time=t,
                    event_type=EventType.MONITOR,
                    priority=5,
                )
                self.event_queue.push(mon_event)
                t += self.monitor_interval

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

        # Schedule an overrun event if HI job will exceed C_LO
        if (
            job.task.criticality == Criticality.HI
            and job.required_execution > job.task.C_LO
            and job.executed_time < job.task.C_LO - 1e-9
        ):
            overrun_needed = (job.task.C_LO - job.executed_time) / self.cpu.speed
            overrun_time = self.current_time + overrun_needed
            overrun_event = Event(
                time=overrun_time,
                event_type=EventType.MODE_CHANGE,
                job=job,
                priority=4,
            )
            self._scheduled_overrun_events[job.job_id] = overrun_event
            self.event_queue.push(overrun_event)

    def _verify_invariants(self) -> None:
        """Verify core safety assertions across the simulation state."""
        # 1. Mode must be valid
        mode = self.mode_controller.current_mode
        assert isinstance(mode, SystemMode) and mode in (
            SystemMode.LO,
            SystemMode.WARNING,
            SystemMode.HI,
            SystemMode.RECOVERY,
        ), f"Mode must be valid SystemMode, got {mode}"

        # 2. Risk must remain in [0, 1]
        if self.risk_history:
            latest_risk = self.risk_history[-1].r_total
            assert -1e-9 <= latest_risk <= 1.0 + 1e-9, (
                f"Risk must remain in [0, 1], got {latest_risk}"
            )

        # 3. Service fraction must remain in [0, 1] and HI tasks cannot be assigned zero service
        for t in self.tasks:
            s = self.degradation_controller.get_service_level(t.task_id)
            assert -1e-9 <= s <= 1.0 + 1e-9, (
                f"Service fraction must remain in [0, 1], task {t.name} got {s}"
            )
            if t.criticality == Criticality.HI:
                assert s > 0.0, f"HI tasks cannot be assigned zero service! Task {t.name} has service {s}"
                # 8. HI task protection must remain active in HI mode
                if mode == SystemMode.HI:
                    assert s == 1.0, f"HI task protection must remain active in HI mode! Task {t.name} has service {s}"

        # 4. Completed jobs cannot execute further & Remaining execution cannot become negative
        for j in self.active_jobs:
            assert j.remaining_execution >= -1e-9, (
                f"Remaining execution cannot become negative: Job {j.job_id} has {j.remaining_execution}"
            )
            if j.completed:
                assert j.remaining_execution <= 1e-9, (
                    f"Completed job {j.job_id} cannot have positive remaining execution: {j.remaining_execution}"
                )

        current = self.cpu.current_job
        if current is not None:
            assert not current.completed or current.remaining_execution <= 1e-9, (
                f"Completed job {current.job_id} cannot execute further on CPU!"
            )
            assert current.remaining_execution >= -1e-9, (
                f"Remaining execution cannot become negative for running job {current.job_id}: {current.remaining_execution}"
            )

        # 7. Virtual deadlines must not be used for LO tasks
        if hasattr(self.scheduler, "_get_effective_deadline"):
            for j in self.active_jobs:
                if j.task.criticality == Criticality.LO:
                    eff_d = self.scheduler._get_effective_deadline(j)
                    assert abs(eff_d - j.absolute_deadline) < 1e-9, (
                        f"Virtual deadlines must not be used for LO tasks! Job {j.job_id} eff_deadline={eff_d} != abs_deadline={j.absolute_deadline}"
                    )

    def _schedule_and_dispatch(self) -> None:
        """Evaluate scheduler decision, enforce assertions, manage CPU assignment & log decision."""
        self.scheduler_invocations += 1
        self.scheduler_decision_count = self.scheduler_invocations
        if self.config.enable_overhead:
            self.cpu.total_busy_time += self.config.scheduler_overhead

        candidate_job = self.scheduler.select_job(self.current_time)
        current_job = self.cpu.current_job

        # Enforce safety assertions
        self._verify_invariants()

        # Capture structured scheduling decision instrumentation
        current_risk = self.risk_history[-1].r_total if self.risk_history else 0.0
        current_mode_str = getattr(
            self.mode_controller.current_mode, "value", str(self.mode_controller.current_mode)
        )
        lo_allocations = {
            self._get_task_short_name(t): self.degradation_controller.get_service_level(t.task_id)
            for t in self.tasks
            if t.criticality == Criticality.LO
        }

        if candidate_job is not None:
            sel_name = self._get_task_short_name(candidate_job.task)
            sel_crit = candidate_job.task.criticality.name
            sel_deadline = candidate_job.absolute_deadline
            sel_eff_deadline = (
                self.scheduler._get_effective_deadline(candidate_job)
                if hasattr(self.scheduler, "_get_effective_deadline")
                else candidate_job.absolute_deadline
            )
            sel_laxity = (
                candidate_job.absolute_deadline
                - self.current_time
                - candidate_job.remaining_execution
            )
            current_eff_deadline = (
                self.scheduler._get_effective_deadline(current_job)
                if (current_job and hasattr(self.scheduler, "_get_effective_deadline"))
                else (current_job.absolute_deadline if current_job else None)
            )
            if current_job is None:
                decision_reason = (
                    f"CPU idle -> Dispatched {sel_name} (effective deadline d'={sel_eff_deadline:.2f}ms)"
                )
            elif current_job == candidate_job:
                decision_reason = (
                    f"Continued executing {sel_name} (effective deadline d'={sel_eff_deadline:.2f}ms)"
                )
            else:
                decision_reason = (
                    f"Preempted {self._get_task_short_name(current_job.task)} -> {sel_name} has earlier effective deadline "
                    f"({sel_eff_deadline:.2f}ms < {current_eff_deadline:.2f}ms)"
                )
        else:
            sel_name = "IDLE"
            sel_crit = "NONE"
            sel_deadline = None
            sel_laxity = None
            decision_reason = "No active ready jobs available; CPU set to IDLE"

        decision_record = {
            "time": self.current_time,
            "mode": current_mode_str,
            "risk": current_risk,
            "selected_job": sel_name,
            "selected_job_criticality": sel_crit,
            "selected_job_deadline": sel_deadline,
            "selected_job_laxity": sel_laxity,
            "lo_service_allocations": lo_allocations,
            "reason": decision_reason,
        }
        self.scheduling_decisions.append(decision_record)
        if hasattr(self.scheduler, "decision_history"):
            self.scheduler.decision_history.append(decision_record)

        alloc_str = ", ".join(f"{k}={v:.2f}" for k, v in lo_allocations.items())
        lax_str = f"{sel_laxity:.2f}ms" if sel_laxity is not None else "N/A"
        ddl_str = f"{sel_deadline:.2f}ms" if sel_deadline is not None else "N/A"
        self._log_timeline(
            self.current_time,
            f"SCHED DECISION: t={self.current_time:.2f} | Mode={current_mode_str} | Risk={current_risk:.4f} | "
            f"Selected={sel_name} ({sel_crit}, D={ddl_str}, Laxity={lax_str}) | LO Alloc=[{alloc_str}] | Reason: {decision_reason}",
        )
        if self.config.verbose:
            print(
                f"[SCHED DECISION] t={self.current_time:5.2f} | Mode={current_mode_str:<8} | Risk={current_risk:.4f} | "
                f"Selected={sel_name:<6} ({sel_crit:<2}) | D={ddl_str} | Laxity={lax_str} | LO=[{alloc_str}] | {decision_reason}"
            )

        if candidate_job is None:
            if current_job is not None and (current_job.completed or current_job.remaining_execution <= 1e-9):
                self.cpu.set_idle(self.current_time)
            return

        if current_job is None:
            # CPU is idle, assign candidate
            self.cpu.assign_job(candidate_job, self.current_time)
            candidate_label = self._get_task_short_name(candidate_job.task)
            self._log_timeline(
                self.current_time,
                f"CPU ALLOCATION: Dispatched {candidate_label} ({candidate_job.job_id})",
            )
            self._schedule_job_completion(candidate_job)
        elif current_job != candidate_job:
            # Check preemption condition
            if self.scheduler.should_preempt(current_job, candidate_job):
                preempted = self.cpu.preempt(self.current_time)
                if preempted:
                    comp_event = self._scheduled_completion_events.pop(preempted.job_id, None)
                    if comp_event:
                        comp_event.cancelled = True
                    ov_event = self._scheduled_overrun_events.pop(preempted.job_id, None)
                    if ov_event:
                        ov_event.cancelled = True
                    self.scheduler.add_job(preempted)
                    preempted_label = self._get_task_short_name(preempted.task)
                    candidate_label = self._get_task_short_name(candidate_job.task)
                    self._log_timeline(
                        self.current_time,
                        f"CPU ALLOCATION: {preempted_label} preempted by {candidate_label}",
                    )
                    self._trigger_risk_evaluation("Preemption")

                self.cpu.assign_job(candidate_job, self.current_time)
                candidate_label = self._get_task_short_name(candidate_job.task)
                self._log_timeline(
                    self.current_time,
                    f"CPU ALLOCATION: Dispatched {candidate_label} ({candidate_job.job_id})",
                )
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
                    if self.cpu.current_job and (self.cpu.current_job.completed or self.cpu.current_job.remaining_execution <= 1e-9):
                        done_job = self.cpu.current_job
                        done_job.remaining_execution = 0.0
                        done_job.completed = True
                        done_job.completion_time = event.time
                        if done_job in self.active_jobs:
                            self.active_jobs.remove(done_job)
                        if done_job not in self.completed_jobs:
                            self.completed_jobs.append(done_job)
                        self.cpu.set_idle(event.time)
                self.clock.advance_to(event.time)
                self.simulation_ended = True
                break

            # Execute running job for elapsed time delta
            delta = event.time - self.current_time
            if delta > 0 and not self.cpu.is_idle():
                self.cpu.execute(delta, self.current_time)
                if event.event_type != EventType.JOB_COMPLETION and self.cpu.current_job and (self.cpu.current_job.completed or self.cpu.current_job.remaining_execution <= 1e-9):
                    done_job = self.cpu.current_job
                    done_job.remaining_execution = 0.0
                    done_job.completed = True
                    done_job.completion_time = event.time
                    if done_job in self.active_jobs:
                        self.active_jobs.remove(done_job)
                    if done_job not in self.completed_jobs:
                        self.completed_jobs.append(done_job)
                    task_label = self._get_task_short_name(done_job.task)
                    self._log_timeline(event.time, f"{task_label} completed execution")
                    self.cpu.set_idle(event.time)
                    comp_ev = self._scheduled_completion_events.pop(done_job.job_id, None)
                    if comp_ev:
                        comp_ev.cancelled = True
                    self.scheduler.on_job_completion(done_job)

            self.clock.advance_to(event.time)
            self._check_mode_switch()

            # Process event by type
            self._process_event(event)

            # Dispatch next job based on scheduler
            self._schedule_and_dispatch()

        self._record_mode_transition_duration(self.current_time, self.current_system_mode_name)
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

            # Apply active degradation if applicable for LO tasks
            if self.degradation_controller and task.criticality == Criticality.LO:
                s = self.degradation_controller.get_service_level(task.task_id)
                if s < 1.0:
                    job.required_execution = task.C_LO * s
                    job.remaining_execution = job.required_execution
                    if s <= 0.0:
                        job.remaining_execution = 0.0
                        job.completed = True

            self.released_jobs.append(job)
            self.active_jobs.append(job)
            task_label = self._get_task_short_name(job.task)
            self._log_timeline(self.current_time, f"{task_label} released")

            self.scheduler.on_job_release(job)
            self._trigger_risk_evaluation("Job Release")

            # Schedule deadline event
            deadline_event = Event(
                time=job.absolute_deadline,
                event_type=EventType.DEADLINE,
                job=job,
                priority=10,
            )
            self.event_queue.push(deadline_event)

            # Schedule deadline proximity event for HI tasks
            if self.enable_monitoring and job.task.criticality == Criticality.HI:
                prox_time = job.absolute_deadline - self.risk_estimator.t_safe
                if prox_time > self.current_time:
                    prox_event = Event(
                        time=prox_time,
                        event_type=EventType.DEADLINE_PROXIMITY,
                        job=job,
                        priority=8,
                    )
                    self.event_queue.push(prox_event)

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
                ov_event = self._scheduled_overrun_events.pop(job.job_id, None)
                if ov_event:
                    ov_event.cancelled = True
                self.cpu.set_idle(self.current_time)
                self._log_timeline(self.current_time, "CPU ALLOCATION: CPU became idle")
                self._trigger_risk_evaluation("Job Completion")

        elif event.event_type == EventType.MONITOR:
            self._trigger_risk_evaluation("Periodic Monitor (0.5ms)")

        elif event.event_type == EventType.DEADLINE:
            job = event.job
            if job and not job.completed:
                job.missed_deadline = True
                job.check_deadline(self.current_time)
                if job not in self.missed_jobs:
                    self.missed_jobs.append(job)
                    task_label = self._get_task_short_name(job.task)
                    self._log_timeline(self.current_time, f"{task_label} missed deadline")
                    self._trigger_risk_evaluation("Deadline Miss")

        elif event.event_type == EventType.DEADLINE_PROXIMITY:
            job = event.job
            if job and not job.completed:
                task_label = self._get_task_short_name(job.task)
                self._trigger_risk_evaluation(f"Deadline Proximity ({task_label})")

        elif event.event_type == EventType.MODE_CHANGE:
            self._check_mode_switch()

        elif event.event_type == EventType.PREEMPTION:
            pass

    def get_summary(self) -> Dict[str, Any]:
        """Generate simulation statistics summary."""
        warmup = getattr(self.config, "warmup_time", 0.0)
        eval_released = [j for j in self.released_jobs if j.release_time >= warmup]
        eval_completed = [j for j in self.completed_jobs if j.release_time >= warmup]
        eval_missed = [j for j in self.missed_jobs if j.release_time >= warmup]

        total_released = len(eval_released)
        total_completed = len(eval_completed)
        total_missed = len(eval_missed)

        hi_missed = len([j for j in eval_missed if j.task.criticality == Criticality.HI])
        lo_released = len([j for j in eval_released if j.task.criticality == Criticality.LO])
        hi_released = total_released - lo_released
        hi_miss_ratio = (hi_missed / hi_released) if hi_released > 0 else 0.0

        lo_completed = len([j for j in eval_completed if j.task.criticality == Criticality.LO])
        lo_completion_ratio = (lo_completed / lo_released) if lo_released > 0 else 1.0

        response_times = [
            j.completion_time - j.release_time
            for j in eval_completed
            if j.completion_time is not None
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0.0
        )
        worst_response_time = max(response_times) if response_times else 0.0

        utilization = (
            (self.cpu.total_busy_time / self.config.duration)
            if self.config.duration > 0
            else 0.0
        )
        utility_metrics = self.degradation_controller.calculate_utility_metrics(
            eval_completed, eval_released
        )

        simulation_time = self.config.duration if self.config.duration > 0 else 1.0
        sched_overhead_time = self.scheduler_invocations * self.config.scheduler_overhead
        risk_overhead_time = self.risk_calculations * self.config.risk_estimation_overhead
        trans_overhead_time = self.mode_transitions * self.config.mode_transition_overhead
        total_overhead_time = (
            (sched_overhead_time + risk_overhead_time + trans_overhead_time)
            if self.config.enable_overhead
            else 0.0
        )
        overhead_pct = (
            (total_overhead_time / simulation_time) * 100.0
            if (self.config.enable_overhead and simulation_time > 0)
            else 0.0
        )

        mode_switches_count = len(self.mode_controller.transitions)
        if hasattr(self.scheduler, "transitions") and getattr(self.scheduler, "transitions"):
            mode_switches_count = max(mode_switches_count, len(getattr(self.scheduler, "transitions")))
        elif hasattr(self.scheduler, "escalated_tasks") and getattr(self.scheduler, "escalated_tasks"):
            mode_switches_count = len(getattr(self.scheduler, "escalated_tasks"))
        elif hasattr(self.scheduler, "current_mode") and getattr(self.scheduler, "current_mode") == Criticality.HI:
            mode_switches_count = max(mode_switches_count, 1)

        warning_dur = self.mode_durations.get("WARNING", 0.0)
        hi_dur = self.mode_durations.get("HI", 0.0)
        rec_dur = self.mode_durations.get("RECOVERY", 0.0)
        rec_time = (sum(self.recovery_episodes) / len(self.recovery_episodes)) if self.recovery_episodes else 0.0

        return {
            "scheduler": self.scheduler.name,
            "duration": self.config.duration,
            "warmup_time": warmup,
            "final_time": self.current_time,
            "total_jobs_released": total_released,
            "completed_jobs_count": total_completed,
            "missed_jobs_count": total_missed,
            "hi_missed_jobs_count": hi_missed,
            "hi_released_jobs_count": hi_released,
            "hi_miss_ratio": hi_miss_ratio,
            "lo_released_jobs_count": lo_released,
            "lo_completed_jobs_count": lo_completed,
            "lo_completion_ratio": lo_completion_ratio,
            "average_response_time": avg_response_time,
            "worst_response_time": worst_response_time,
            "cpu_busy_time": self.cpu.total_busy_time,
            "cpu_utilization": utilization,
            "LO_utility": utility_metrics["LO_utility"],
            "maximum_possible_LO_utility": utility_metrics["maximum_possible_LO_utility"],
            "LO_utility_ratio": utility_metrics["LO_utility_ratio"],
            "warning_duration": warning_dur,
            "hi_duration": hi_dur,
            "recovery_duration": rec_dur,
            "recovery_time": rec_time,
            "service_change_log": self.degradation_controller.service_change_log,
            "mode_switches_count": mode_switches_count,
            "enable_overhead": self.config.enable_overhead,
            "scheduler_invocations": self.scheduler_invocations,
            "scheduler_decision_count": self.scheduler_decision_count,
            "risk_calculations": self.risk_calculations,
            "risk_calculation_count": self.risk_calculation_count,
            "mode_transitions": self.mode_transitions,
            "mode_transition_count": self.mode_transition_count,
            "scheduler_overhead_time": sched_overhead_time,
            "scheduler_overhead": sched_overhead_time,
            "risk_overhead_time": risk_overhead_time,
            "risk_overhead": risk_overhead_time,
            "mode_transition_overhead_time": trans_overhead_time,
            "transition_overhead": trans_overhead_time,
            "total_overhead_time": total_overhead_time,
            "total_overhead": total_overhead_time,
            "overhead_percentage": overhead_pct,
            "timeline": self.timeline,
            "risk_history": self.risk_history,
            "state_timeline": self.state_timeline,
            "scheduling_decisions": self.scheduling_decisions,
        }
