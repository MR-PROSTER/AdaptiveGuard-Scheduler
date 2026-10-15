"""
Unit tests for the Ablation Framework (Configs A through F).
"""

import pytest
from config.ablation_config import AblationConfig, get_ablation_config
from schedulers.adaptive_guard import AdaptiveGuardScheduler
from workloads.fixed_workload import get_fixed_workload
from simulator.simulation import Simulation
from config.default_config import SimulationConfig


def test_ablation_component_flags():
    """Verify each ablation configuration has exactly the specified components enabled/disabled."""
    cfg_a = get_ablation_config("A")
    assert not cfg_a.enable_risk
    assert not cfg_a.enable_proactive_warning
    assert not cfg_a.enable_degradation
    assert not cfg_a.enable_utility_degradation
    assert not cfg_a.enable_hysteresis
    assert not cfg_a.enable_recovery

    cfg_b = get_ablation_config("B")
    assert not cfg_b.enable_risk
    assert not cfg_b.enable_proactive_warning
    assert cfg_b.enable_degradation
    assert not cfg_b.enable_utility_degradation
    assert not cfg_b.enable_hysteresis
    assert not cfg_b.enable_recovery

    cfg_c = get_ablation_config("C")
    assert cfg_c.enable_risk
    assert cfg_c.enable_proactive_warning
    assert not cfg_c.enable_degradation
    assert not cfg_c.enable_utility_degradation
    assert not cfg_c.enable_hysteresis
    assert not cfg_c.enable_recovery

    cfg_d = get_ablation_config("D")
    assert not cfg_d.enable_risk
    assert not cfg_d.enable_proactive_warning
    assert cfg_d.enable_degradation
    assert cfg_d.enable_utility_degradation
    assert not cfg_d.enable_hysteresis
    assert not cfg_d.enable_recovery

    cfg_e = get_ablation_config("E")
    assert cfg_e.enable_risk
    assert cfg_e.enable_proactive_warning
    assert cfg_e.enable_degradation
    assert cfg_e.enable_utility_degradation
    assert not cfg_e.enable_hysteresis
    assert not cfg_e.enable_recovery

    cfg_f = get_ablation_config("F")
    assert cfg_f.enable_risk
    assert cfg_f.enable_proactive_warning
    assert cfg_f.enable_degradation
    assert cfg_f.enable_utility_degradation
    assert cfg_f.enable_hysteresis
    assert cfg_f.enable_recovery


def test_independent_component_disabling():
    """Verify that every single ablation flag can be modified independently on an AblationConfig."""
    cfg = AblationConfig()
    cfg.enable_risk = False
    assert not cfg.enable_risk
    cfg.enable_utility_degradation = False
    assert not cfg.enable_utility_degradation
    cfg.enable_hysteresis = False
    assert not cfg.enable_hysteresis
    cfg.enable_recovery = False
    assert not cfg.enable_recovery
    cfg.enable_proactive_warning = False
    assert not cfg.enable_proactive_warning


def test_b_and_d_not_identical():
    """Verify that B (generic degradation) and D (utility degradation) produce distinct behavior."""
    tasks_b = get_fixed_workload()
    sched_b = AdaptiveGuardScheduler(tasks=tasks_b, ablation_config=get_ablation_config("B"))
    sim_b = Simulation(tasks=tasks_b, config=SimulationConfig(duration=200.0, verbose=False), scheduler=sched_b, scenario="BOTH_OVERRUN", overload_until_seq=3)
    res_b = sim_b.run()

    tasks_d = get_fixed_workload()
    sched_d = AdaptiveGuardScheduler(tasks=tasks_d, ablation_config=get_ablation_config("D"))
    sim_d = Simulation(tasks=tasks_d, config=SimulationConfig(duration=200.0, verbose=False), scheduler=sched_d, scenario="BOTH_OVERRUN", overload_until_seq=3)
    res_d = sim_d.run()

    # B gives uniform 0.50 service to all LO tasks -> 0.50 utility ratio
    # D prioritizes Telemetry (utility density 16.67) -> higher utility ratio, lower completion count
    assert res_b["lo_completion_ratio"] != res_d["lo_completion_ratio"]
    assert abs(res_b["LO_utility_ratio"] - res_d["LO_utility_ratio"]) > 0.05


def test_e_and_f_not_identical():
    """Verify that E (no hysteresis, no recovery) and F (full AdaptiveGuard) produce distinct behavior."""
    tasks_e = get_fixed_workload()
    sched_e = AdaptiveGuardScheduler(tasks=tasks_e, ablation_config=get_ablation_config("E"))
    sim_e = Simulation(tasks=tasks_e, config=SimulationConfig(duration=200.0, verbose=False), scheduler=sched_e, scenario="BOTH_OVERRUN", overload_until_seq=3)
    res_e = sim_e.run()

    tasks_f = get_fixed_workload()
    sched_f = AdaptiveGuardScheduler(tasks=tasks_f, ablation_config=get_ablation_config("F"))
    sim_f = Simulation(tasks=tasks_f, config=SimulationConfig(duration=200.0, verbose=False), scheduler=sched_f, scenario="BOTH_OVERRUN", overload_until_seq=3)
    res_f = sim_f.run()

    # E lacks hysteresis, so mode chattering occurs (significantly more mode switches)
    assert res_e["mode_switches_count"] != res_f["mode_switches_count"]
    assert res_e["mode_switches_count"] > res_f["mode_switches_count"]
