import pytest
from controllers.mode_controller import (
    SystemMode,
    ModeTransition,
    AdaptiveGuardModeController,
)


def test_transition_lo_to_warning():
    """Verify LO -> WARNING transition when 0.60 <= risk < 0.80."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.LO)
    assert mc.current_mode == SystemMode.LO

    mode = mc.update(current_time=1.0, risk=0.65)
    assert mode == SystemMode.WARNING
    assert mc.current_mode == SystemMode.WARNING
    assert len(mc.transitions) == 1

    trans = mc.transitions[0]
    assert trans.time == 1.0
    assert trans.old_mode == SystemMode.LO
    assert trans.new_mode == SystemMode.WARNING
    assert trans.risk == 0.65
    assert "WARNING_ENTER" in trans.reason


def test_transition_lo_to_hi():
    """Verify LO -> HI transition when risk >= 0.80."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.LO)
    mode = mc.update(current_time=1.0, risk=0.85)
    assert mode == SystemMode.HI
    assert mc.transitions[0].old_mode == SystemMode.LO
    assert mc.transitions[0].new_mode == SystemMode.HI


def test_transition_warning_to_lo():
    """Verify WARNING -> LO transition when risk < 0.40."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.WARNING)
    mode = mc.update(current_time=2.0, risk=0.35)
    assert mode == SystemMode.LO
    assert mc.transitions[0].old_mode == SystemMode.WARNING
    assert mc.transitions[0].new_mode == SystemMode.LO


def test_transition_warning_to_hi():
    """Verify WARNING -> HI transition when risk >= 0.80."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.WARNING)
    mode = mc.update(current_time=2.0, risk=0.82)
    assert mode == SystemMode.HI
    assert mc.transitions[0].old_mode == SystemMode.WARNING
    assert mc.transitions[0].new_mode == SystemMode.HI


def test_transition_warning_stay():
    """Verify WARNING mode is maintained when 0.40 <= risk < 0.80."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.WARNING)
    mode = mc.update(current_time=2.0, risk=0.55)
    assert mode == SystemMode.WARNING
    assert len(mc.transitions) == 0


def test_transition_hi_to_recovery_after_5ms_hold():
    """
    REQUIRED TEST: HI -> RECOVERY occurs ONLY after 5.0 ms continuously below 0.40 threshold.
    """
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.HI, recovery_hold_time=5.0)

    # t=10.0: Risk drops to 0.35 (below 0.40)
    assert mc.update(current_time=10.0, risk=0.35) == SystemMode.HI
    assert mc.low_risk_start_time == 10.0

    # t=12.0 (elapsed 2.0ms): Should still stay in HI
    assert mc.update(current_time=12.0, risk=0.35) == SystemMode.HI
    assert len(mc.transitions) == 0

    # t=14.9 (elapsed 4.9ms): Should still stay in HI
    assert mc.update(current_time=14.9, risk=0.35) == SystemMode.HI
    assert len(mc.transitions) == 0

    # t=15.0 (elapsed 5.0ms): Continuously below 0.40 for 5.0ms -> Transition to RECOVERY!
    assert mc.update(current_time=15.0, risk=0.35) == SystemMode.RECOVERY
    assert len(mc.transitions) == 1

    trans = mc.transitions[0]
    assert trans.old_mode == SystemMode.HI
    assert trans.new_mode == SystemMode.RECOVERY
    assert trans.time == 15.0


def test_temporary_risk_decrease_resets_hold_timer():
    """
    REQUIRED TEST: Test that a temporary risk decrease does not immediately recover
    and that a spike above 0.40 resets the 5.0 ms hold timer.
    """
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.HI, recovery_hold_time=5.0)

    # t=10.0: Risk drops below 0.40 (timer starts at 10.0)
    assert mc.update(current_time=10.0, risk=0.30) == SystemMode.HI

    # t=13.0 (elapsed 3.0ms): Stays HI
    assert mc.update(current_time=13.0, risk=0.30) == SystemMode.HI

    # t=14.0: Risk spikes to 0.50 (> 0.40) -> Timer MUST reset!
    assert mc.update(current_time=14.0, risk=0.50) == SystemMode.HI
    assert mc.low_risk_start_time is None

    # t=15.0: Risk drops below 0.40 again (timer restarts at 15.0)
    assert mc.update(current_time=15.0, risk=0.30) == SystemMode.HI
    assert mc.low_risk_start_time == 15.0

    # t=18.0 (elapsed 3.0ms since restart): Stays HI
    assert mc.update(current_time=18.0, risk=0.30) == SystemMode.HI
    assert len(mc.transitions) == 0

    # t=20.0 (elapsed 5.0ms since restart): Transition to RECOVERY!
    assert mc.update(current_time=20.0, risk=0.30) == SystemMode.RECOVERY
    assert len(mc.transitions) == 1
    assert mc.transitions[0].time == 20.0


def test_transition_recovery_to_warning():
    """Verify RECOVERY -> WARNING transition when risk > 0.40."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.RECOVERY)
    mode = mc.update(current_time=25.0, risk=0.45)
    assert mode == SystemMode.WARNING
    assert mc.transitions[0].old_mode == SystemMode.RECOVERY
    assert mc.transitions[0].new_mode == SystemMode.WARNING


def test_transition_recovery_to_hi():
    """Verify RECOVERY -> HI transition when risk >= 0.80."""
    mc = AdaptiveGuardModeController(initial_mode=SystemMode.RECOVERY)
    mode = mc.update(current_time=25.0, risk=0.85)
    assert mode == SystemMode.HI
    assert mc.transitions[0].old_mode == SystemMode.RECOVERY
    assert mc.transitions[0].new_mode == SystemMode.HI
