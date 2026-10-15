"""
AdaptiveGuard Scheduler.

Integrates:
1. Earliest Deadline First with Virtual Deadlines (EDF-VD)
2. Runtime Monitoring & Laxity / Overrun tracking
3. Proactive Multi-Factor Risk Estimation
4. Dynamic Mode Transitions with Hysteresis (LO -> WARNING -> HI -> RECOVERY)
5. Utility-Aware LO Task Degradation (Ranking by utility density)
6. Gradual LO Task Recovery (Step-by-step restoration: 0.00 -> 0.25 -> 0.50 -> 0.75 -> 1.00)

Complete Control Loop:
    Job release
        ↓
    Ready queue
        ↓
    EDF-VD priority
        ↓
    CPU execution
        ↓
    Runtime Monitor
        ↓
    Risk Estimator
        ↓
    Mode Controller
        ↓
    Utility-Aware Degradation
        ↓
    Updated scheduling decision
        ↓
    CPU execution
"""

from typing import List, Optional, Tuple, Any, Dict
from simulator.job import Job
from simulator.task import Task, Criticality
from schedulers.base_scheduler import BaseScheduler
from schedulers.edf_vd import calculate_x, virtual_deadline
from controllers.mode_controller import SystemMode, AdaptiveGuardModeController, is_hi_mode
from controllers.runtime_monitor import RuntimeMonitor
from controllers.risk_estimator import RiskEstimator
from controllers.degradation_controller import UtilityAwareDegradationController


class AdaptiveGuardScheduler(BaseScheduler):
    """
    Complete AdaptiveGuard Scheduler engine.
    """

    def __init__(
        self,
        tasks: Optional[List[Task]] = None,
        x: Optional[float] = None,
        initial_mode: SystemMode = SystemMode.LO,
        runtime_monitor: Optional[RuntimeMonitor] = None,
        risk_estimator: Optional[RiskEstimator] = None,
        mode_controller: Optional[AdaptiveGuardModeController] = None,
        degradation_controller: Optional[UtilityAwareDegradationController] = None,
        ablation_config: Optional[Any] = None,
    ) -> None:
        super().__init__(name="AdaptiveGuard")
        self.tasks: List[Task] = tasks or []
        assert isinstance(initial_mode, SystemMode), f"Mode must be valid SystemMode, got {initial_mode}"
        self.current_mode: SystemMode = initial_mode
        self.ablation_config: Optional[Any] = ablation_config

        # Initialize or bind integrated controllers with ablation_config
        self.runtime_monitor: RuntimeMonitor = (
            runtime_monitor if runtime_monitor is not None else RuntimeMonitor()
        )
        self.risk_estimator: RiskEstimator = (
            risk_estimator if risk_estimator is not None else RiskEstimator()
        )
        self.mode_controller: AdaptiveGuardModeController = (
            mode_controller
            if mode_controller is not None
            else AdaptiveGuardModeController(ablation_config=ablation_config)
        )
        self.degradation_controller: UtilityAwareDegradationController = (
            degradation_controller
            if degradation_controller is not None
            else UtilityAwareDegradationController(tasks=self.tasks, ablation_config=ablation_config)
        )

        if x is not None:
            self.x: float = x
        elif self.tasks:
            self.x = calculate_x(self.tasks)
        else:
            self.x = 1.0

        self.ready_queue: List[Job] = []
        self.decision_history: List[Dict[str, Any]] = []

    def set_mode(self, new_mode: Any) -> None:
        """Update active system mode with validation assertions."""
        if isinstance(new_mode, SystemMode):
            mapped_mode = new_mode
        elif is_hi_mode(new_mode):
            mapped_mode = SystemMode.HI
        elif isinstance(new_mode, str) and hasattr(SystemMode, new_mode.upper()):
            mapped_mode = SystemMode[new_mode.upper()]
        else:
            mapped_mode = SystemMode.LO

        assert isinstance(mapped_mode, SystemMode), f"Mode must be valid SystemMode, got {mapped_mode}"

        if self.current_mode != mapped_mode:
            self.current_mode = mapped_mode
            if self.current_mode == SystemMode.HI and self.degradation_controller:
                # Shed LO tasks whose service level is 0.0
                self.ready_queue = [
                    j for j in self.ready_queue
                    if j.task.criticality == Criticality.HI or self.degradation_controller.get_service_level(j.task.task_id) > 0.0
                ]

    def _get_service_level(self, task_id: int) -> float:
        """Helper to get current service level for a task with safety bounds check."""
        if self.degradation_controller:
            s = self.degradation_controller.get_service_level(task_id)
            assert -1e-9 <= s <= 1.0 + 1e-9, f"Service fraction must remain in [0,1], got {s}"
            return s
        return 1.00

    def _get_effective_deadline(self, job: Job) -> float:
        """
        Calculate effective deadline for job:
        - In LO, WARNING, or RECOVERY mode: HI tasks use virtual deadline d'_i.
        - In HI mode: HI tasks use actual deadline (with LO tasks degraded/shed).
        - LO tasks ALWAYS use actual deadline (Virtual deadlines must not be used for LO tasks).
        """
        if job.task.criticality == Criticality.LO:
            eff_d = job.absolute_deadline
            assert abs(eff_d - job.absolute_deadline) < 1e-9, (
                f"Virtual deadlines must not be used for LO tasks! Got {eff_d} vs {job.absolute_deadline}"
            )
            return eff_d

        if self.current_mode in (SystemMode.LO, SystemMode.WARNING, SystemMode.RECOVERY) and job.task.criticality == Criticality.HI:
            return virtual_deadline(job, self.x, Criticality.LO)
        return job.absolute_deadline

    def add_job(self, job: Job) -> None:
        """Add job to ready queue if not already present and not completed."""
        if job.completed:
            return

        assert not job.completed, f"Completed job {job.job_id} cannot be added to ready queue!"
        assert job.remaining_execution >= -1e-9, (
            f"Remaining execution cannot become negative: {job.remaining_execution}"
        )

        if job not in self.ready_queue:
            # If service level is 0, do not admit LO job
            if job.task.criticality == Criticality.LO and self._get_service_level(job.task.task_id) <= 0.0:
                job.remaining_execution = 0.0
                job.completed = True
                return
            self.ready_queue.append(job)

    def remove_job(self, job: Job) -> None:
        """Remove job from ready queue."""
        if job in self.ready_queue:
            self.ready_queue.remove(job)

    def select_job(self, current_time: float) -> Optional[Job]:
        """
        Select highest-priority job from ready queue.

        Priority Order:
          1. Smallest effective deadline (EDF-VD)
          2. HI criticality first
          3. Earlier release time
          4. Task ID
        """
        # Assertion: Mode must be valid
        assert isinstance(self.current_mode, SystemMode), (
            f"Mode must be valid SystemMode, got {self.current_mode}"
        )

        # Assertion: HI task protection must remain active in HI mode & HI tasks cannot be assigned zero service
        if self.degradation_controller:
            for t in self.tasks:
                if t.criticality == Criticality.HI:
                    s = self._get_service_level(t.task_id)
                    assert s > 0.0, f"HI tasks cannot be assigned zero service! Task {t.name} has service {s}"
                    if self.current_mode == SystemMode.HI:
                        assert s == 1.0, f"HI task protection must remain active in HI mode! Task {t.name} has service {s}"

        active_ready = [
            j for j in self.ready_queue
            if not j.completed and j.remaining_execution > 1e-9
        ]

        # Assertion: Completed jobs cannot execute further & Remaining execution cannot become negative
        for j in active_ready:
            assert not j.completed, f"Completed job {j.job_id} cannot execute further!"
            assert j.remaining_execution >= -1e-9, (
                f"Remaining execution cannot become negative: {j.remaining_execution}"
            )

        if self.current_mode == SystemMode.HI and self.degradation_controller:
            active_ready = [
                j for j in active_ready
                if j.task.criticality == Criticality.HI or self._get_service_level(j.task.task_id) > 0.0
            ]

        if not active_ready:
            return None

        chosen = min(
            active_ready,
            key=lambda j: (
                self._get_effective_deadline(j),
                0 if j.task.criticality == Criticality.HI else 1,
                j.release_time,
                j.task.task_id,
            ),
        )
        assert not chosen.completed, f"Selected job {chosen.job_id} must not be completed!"
        return chosen

    def should_preempt(self, current_job: Optional[Job], candidate_job: Optional[Job]) -> bool:
        """
        Determine whether candidate job should preempt current job.
        """
        if current_job is None:
            return True
        if candidate_job is None:
            return False
        if current_job == candidate_job:
            return False

        current_eff = self._get_effective_deadline(current_job)
        candidate_eff = self._get_effective_deadline(candidate_job)

        current_key = (
            current_eff,
            0 if current_job.task.criticality == Criticality.HI else 1,
            current_job.release_time,
            current_job.task.task_id,
        )
        candidate_key = (
            candidate_eff,
            0 if candidate_job.task.criticality == Criticality.HI else 1,
            candidate_job.release_time,
            candidate_job.task.task_id,
        )

        return candidate_key < current_key

    def on_job_release(self, job: Job) -> None:
        """Handle job release event."""
        self.add_job(job)

    def on_job_completion(self, job: Job) -> None:
        """Handle job completion event."""
        self.remove_job(job)
