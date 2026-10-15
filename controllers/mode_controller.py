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
    r_util: float = 0.0
    r_laxity: float = 0.0
    r_overrun: float = 0.0
    r_deadline: float = 0.0

    @property
    def timestamp(self) -> float:
        return self.time



def is_hi_mode(mode: Any) -> bool:
    """Check if given mode represents a HI mode across SystemMode and Criticality."""
    if isinstance(mode, SystemMode):
        return mode == SystemMode.HI
    if hasattr(mode, "value"):
        return str(mode.value).upper() == "HI"
    if isinstance(mode, str):
        return mode.upper() in ("HI", "HIGH")
    return False


def is_lo_mode(mode: Any) -> bool:
    """Check if given mode represents a LO / non-HI mode across SystemMode and Criticality."""
    if isinstance(mode, SystemMode):
        return mode in (SystemMode.LO, SystemMode.WARNING, SystemMode.RECOVERY)
    if hasattr(mode, "value"):
        return str(mode.value).upper() in ("LO", "LOW", "WARNING", "RECOVERY")
    if isinstance(mode, str):
        return mode.upper() in ("LO", "LOW", "WARNING", "RECOVERY")
    return False


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
        ablation_config: Optional[Any] = None,
    ) -> None:
        self.current_mode: SystemMode = initial_mode
        self.warning_enter: float = warning_enter
        self.hi_enter: float = hi_enter
        self.recovery_enter: float = recovery_enter
        self.recovery_hold_time: float = recovery_hold_time
        self.ablation_config = ablation_config

        self.low_risk_start_time: Optional[float] = None
        self.transitions: List[ModeTransition] = []

    def _record_transition(
        self,
        time: float,
        old_mode: SystemMode,
        new_mode: SystemMode,
        risk: float,
        reason: str,
        r_util: float = 0.0,
        r_laxity: float = 0.0,
        r_overrun: float = 0.0,
        r_deadline: float = 0.0,
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
            r_util=r_util,
            r_laxity=r_laxity,
            r_overrun=r_overrun,
            r_deadline=r_deadline,
        )
        self.transitions.append(transition)

    def update(
        self,
        current_time: float,
        risk: float,
        recovery_completed: bool = False,
        r_util: float = 0.0,
        r_laxity: float = 0.0,
        r_overrun: float = 0.0,
        r_deadline: float = 0.0,
    ) -> SystemMode:
        """
        Evaluate current risk against thresholds and update system mode with hysteresis.

        Args:
            current_time (float): Current simulation timestamp (ms).
            risk (float): Calculated total risk score [0.0, 1.0].
            recovery_completed (bool): True if gradual recovery has fully restored all LO tasks.
            r_util (float): Short-horizon utilization risk.
            r_laxity (float): Minimum HI task laxity risk.
            r_overrun (float): Maximum HI task overrun risk.
            r_deadline (float): HI deadline proximity risk.

        Returns:
            SystemMode: Updated current system mode.
        """
        old_mode = self.current_mode

        enable_warning = (
            self.ablation_config.enable_proactive_warning
            if self.ablation_config is not None
            else True
        )
        enable_hysteresis = (
            self.ablation_config.enable_hysteresis
            if self.ablation_config is not None
            else True
        )
        enable_recovery = (
            self.ablation_config.enable_recovery
            if self.ablation_config is not None
            else True
        )

        if old_mode == SystemMode.LO:
            if risk >= self.hi_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.HI,
                    risk,
                    f"Risk ({risk:.3f}) >= HI_ENTER threshold ({self.hi_enter:.2f})",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )
            elif enable_warning and risk >= self.warning_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.WARNING,
                    risk,
                    f"Risk ({risk:.3f}) >= WARNING_ENTER threshold ({self.warning_enter:.2f})",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )

        elif old_mode == SystemMode.WARNING:
            if risk >= self.hi_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.HI,
                    risk,
                    f"Risk ({risk:.3f}) >= HI_ENTER threshold ({self.hi_enter:.2f})",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )
            else:
                exit_threshold = self.recovery_enter if enable_hysteresis else self.warning_enter
                if risk < exit_threshold:
                    self._record_transition(
                        current_time,
                        old_mode,
                        SystemMode.LO,
                        risk,
                        f"Risk ({risk:.3f}) < exit threshold ({exit_threshold:.2f})",
                        r_util,
                        r_laxity,
                        r_overrun,
                        r_deadline,
                    )

        elif old_mode == SystemMode.HI:
            if not enable_hysteresis:
                if risk < self.hi_enter:
                    if enable_recovery:
                        target_mode = SystemMode.RECOVERY
                    elif enable_warning and risk >= self.warning_enter:
                        target_mode = SystemMode.WARNING
                    else:
                        target_mode = SystemMode.LO
                    self._record_transition(
                        current_time,
                        old_mode,
                        target_mode,
                        risk,
                        f"Immediate HI exit without hysteresis (Risk={risk:.3f} < {self.hi_enter:.2f})",
                        r_util,
                        r_laxity,
                        r_overrun,
                        r_deadline,
                    )
            else:
                if risk > self.recovery_enter:
                    self.low_risk_start_time = None
                else:
                    if self.low_risk_start_time is None:
                        self.low_risk_start_time = current_time

                    elapsed = current_time - self.low_risk_start_time
                    if elapsed >= self.recovery_hold_time - 1e-9:
                        target_mode = SystemMode.RECOVERY if enable_recovery else (
                            SystemMode.WARNING if (enable_warning and risk >= self.warning_enter) else SystemMode.LO
                        )
                        self._record_transition(
                            current_time,
                            old_mode,
                            target_mode,
                            risk,
                            f"Risk ({risk:.3f}) <= {self.recovery_enter:.2f} continuously for {self.recovery_hold_time:.1f}ms",
                            r_util,
                            r_laxity,
                            r_overrun,
                            r_deadline,
                        )

        elif old_mode == SystemMode.RECOVERY:
            if not enable_recovery:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.LO,
                    risk,
                    "Recovery disabled by ablation configuration",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )
            elif risk >= self.hi_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.HI,
                    risk,
                    f"Risk ({risk:.3f}) >= HI_ENTER threshold ({self.hi_enter:.2f})",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )
            elif risk > self.recovery_enter:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.WARNING,
                    risk,
                    f"Risk ({risk:.3f}) > RECOVERY_ENTER threshold ({self.recovery_enter:.2f})",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )
            elif recovery_completed:
                self._record_transition(
                    current_time,
                    old_mode,
                    SystemMode.LO,
                    risk,
                    f"Recovery completed; service restored to full level in LO mode",
                    r_util,
                    r_laxity,
                    r_overrun,
                    r_deadline,
                )
        return self.current_mode
