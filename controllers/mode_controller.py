"""
AdaptiveGuard Mode Controller.

Manages system criticality state transitions with hysteresis protection:
  LO <-> WARNING <-> HI -> RECOVERY -> WARNING

Thresholds (configurable project-design parameters):
  WARNING_ENTER      = 0.60
  HI_ENTER           = 0.80
  RECOVERY_ENTER     = 0.40
  RECOVERY_HOLD_TIME = 5.0 ms

Hysteresis Rules:
  - HI -> RECOVERY occurs ONLY after total risk remains <= 0.40 continuously for 5.0 ms.
  - A temporary risk drop below 0.40 that spikes back above 0.40 before 5.0 ms resets the hold timer.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional


class SystemMode(Enum):
    LO = "LO"
    WARNING = "WARNING"
    HI = "HI"
    RECOVERY = "RECOVERY"


@dataclass
class ModeTransition:
    """
    Record of a system mode transition event.
    """

    time: float
    old_mode: SystemMode
    new_mode: SystemMode
    risk: float
    reason: str


class AdaptiveGuardModeController:
    """
    AdaptiveGuard Mode Controller engine.

    Attributes:
        current_mode (SystemMode): Current system mode (default: SystemMode.LO)
        warning_enter (float): Risk threshold to enter WARNING mode (default: 0.60)
        hi_enter (float): Risk threshold to enter HI mode (default: 0.80)
        recovery_enter (float): Risk threshold below which recovery can initiate (default: 0.40)
        recovery_hold_time (float): Continuous duration (ms) below threshold to trigger HI -> RECOVERY (default: 5.0 ms)
    """

    def __init__(
        self,
        initial_mode: SystemMode = SystemMode.LO,
        warning_enter: float = 0.60,
        hi_enter: float = 0.80,
        recovery_enter: float = 0.40,
        recovery_hold_time: float = 5.0,
    ) -> None:
        self.current_mode: SystemMode = initial_mode
        self.warning_enter: float = warning_enter
        self.hi_enter: float = hi_enter
        self.recovery_enter: float = recovery_enter
        self.recovery_hold_time: float = recovery_hold_time

        self.low_risk_start_time: Optional[float] = None
        self.transitions: List[ModeTransition] = []

    def _record_transition(
        self, time: float, old_mode: SystemMode, new_mode: SystemMode, risk: float, reason: str
    ) -> None:
        """Record and apply a mode transition."""
        self.current_mode = new_mode
        self.low_risk_start_time = None
        transition = ModeTransition(
            time=time,
            old_mode=old_mode,
            new_mode=new_mode,
            risk=risk,
            reason=reason,
        )
        self.transitions.append(transition)

    def update(self, current_time: float, risk: float) -> SystemMode:
        """
        Evaluate current risk against thresholds and update system mode with hysteresis.

        Args:
            current_time (float): Current simulation timestamp (ms).
            risk (float): Calculated total risk score [0.0, 1.0].

        Returns:
            SystemMode: Updated current system mode.
        """
        old_mode = self.current_mode

        if old_mode == SystemMode.LO:
            if risk >= self.hi_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.HI,
                    risk,
                    f"Risk ({risk:.3f}) >= HI_ENTER threshold ({self.hi_enter:.2f})",
                )
            elif risk >= self.warning_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.WARNING,
                    risk,
                    f"Risk ({risk:.3f}) >= WARNING_ENTER threshold ({self.warning_enter:.2f})",
                )

        elif old_mode == SystemMode.WARNING:
            if risk >= self.hi_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.HI,
                    risk,
                    f"Risk ({risk:.3f}) >= HI_ENTER threshold ({self.hi_enter:.2f})",
                )
            elif risk < self.recovery_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.LO,
                    risk,
                    f"Risk ({risk:.3f}) < RECOVERY_ENTER threshold ({self.recovery_enter:.2f})",
                )

        elif old_mode == SystemMode.HI:
            if risk > self.recovery_enter:
                # Reset hold timer if risk exceeds recovery threshold
                self.low_risk_start_time = None
            else:
                # Risk <= recovery_enter (0.40)
                if self.low_risk_start_time is None:
                    self.low_risk_start_time = current_time

                elapsed = current_time - self.low_risk_start_time
                if elapsed >= self.recovery_hold_time - 1e-9:
                    self._record_transition(
                        current_time,
                        old_mode,
                        SystemMode.RECOVERY,
                        risk,
                        f"Risk ({risk:.3f}) <= {self.recovery_enter:.2f} continuously for {self.recovery_hold_time:.1f}ms",
                    )

        elif old_mode == SystemMode.RECOVERY:
            if risk >= self.hi_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.HI,
                    risk,
                    f"Risk ({risk:.3f}) >= HI_ENTER threshold ({self.hi_enter:.2f})",
                )
            elif risk > self.recovery_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.WARNING,
                    risk,
                    f"Risk ({risk:.3f}) > RECOVERY_ENTER threshold ({self.recovery_enter:.2f})",
                )

        return self.current_mode
