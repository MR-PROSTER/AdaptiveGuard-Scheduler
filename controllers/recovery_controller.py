"""
Gradual Recovery Controller for AdaptiveGuard.

Manages step-by-step restoration of LO task service levels upon entering RECOVERY mode:
  0.00 -> 0.25 -> 0.50 -> 0.75 -> 1.00

Key Rules:
- Higher utility-density LO tasks are restored FIRST during gradual recovery.
- Do NOT restore everything immediately.
- If risk rises above 0.40 during recovery, RECOVERY mode transitions to WARNING or HI.
"""

from typing import Dict, List, Optional
from simulator.task import Task, Criticality
from controllers.mode_controller import SystemMode
from controllers.degradation_controller import (
    ALLOWED_SERVICE_LEVELS,
    DegradationController,
    rank_lo_tasks_by_utility_density,
)

RECOVERY_STEPS = (0.00, 0.25, 0.50, 0.75, 1.00)


class GradualRecoveryController:
    """
    Gradual Recovery Controller engine.
    """

    def __init__(
        self,
        tasks: List[Task],
        degradation_controller: DegradationController,
        step_interval: float = 1.0,
    ) -> None:
        self.tasks: List[Task] = tasks
        self.degradation_controller: DegradationController = degradation_controller
        self.step_interval: float = step_interval

        self.recovery_start_time: Optional[float] = None
        self.is_recovering: bool = False
        self.current_step_index: int = 0

    def start_recovery(self, current_time: float) -> None:
        """Initiate gradual recovery sequence."""
        self.recovery_start_time = current_time
        self.is_recovering = True
        self.current_step_index = 0

    def stop_recovery(self) -> None:
        """Stop/cancel recovery sequence."""
        self.recovery_start_time = None
        self.is_recovering = False
        self.current_step_index = 0

    def update_recovery(
        self, current_time: float, mode: SystemMode, risk: float
    ) -> Dict[int, float]:
        """
        Step-by-step restoration of LO task service levels during RECOVERY mode.

        Restores higher utility-density LO tasks FIRST through steps:
            0.00 -> 0.25 -> 0.50 -> 0.75 -> 1.00
        """
        if mode != SystemMode.RECOVERY:
            if self.is_recovering:
                self.stop_recovery()
            return self.degradation_controller.current_service_levels

        if not self.is_recovering:
            self.start_recovery(current_time)

        elapsed = current_time - self.recovery_start_time
        target_step_idx = int(elapsed // self.step_interval)
        target_step_idx = min(len(RECOVERY_STEPS) - 1, target_step_idx)

        lo_ranked = rank_lo_tasks_by_utility_density(self.tasks)
        num_lo = len(lo_ranked)

        service_levels: Dict[int, float] = {}

        for idx, t in enumerate(lo_ranked):
            # Higher density tasks (smaller idx) restore faster
            task_step_idx = min(len(RECOVERY_STEPS) - 1, target_step_idx + (num_lo - 1 - idx))
            target_service = RECOVERY_STEPS[task_step_idx]

            self.degradation_controller.set_task_service_level(
                current_time,
                t,
                target_service,
                f"RECOVERY mode gradual restoration (step {target_service:.2f})",
            )
            service_levels[t.task_id] = self.degradation_controller.get_service_level(t.task_id)

        # Check if all LO tasks reached 1.00
        all_full = all(s >= 1.00 for s in service_levels.values())
        if all_full:
            self.stop_recovery()

        return service_levels
