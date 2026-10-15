"""
Ablation Study Configuration Object.

Explicitly defines which components of AdaptiveGuard are enabled/disabled:
- A: EDF-VD (no degradation, no proactive risk)
- B: EDF-VD + generic degraded LO service (generic degradation, no proactive risk)
- C: EDF-VD + proactive risk (risk detection, no utility-aware degradation)
- D: EDF-VD + utility-aware degradation (utility-aware degradation, no proactive risk)
- E: EDF-VD + proactive risk + degradation (risk + utility-aware degradation, no hysteresis, no recovery)
- F: Full AdaptiveGuard (risk + utility-aware degradation + hysteresis + gradual recovery)
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class AblationConfig:
    """
    Configuration flags to control each modular component of the scheduling framework.
    """
    code: str = "F"
    name: str = "Full AdaptiveGuard"
    enable_risk: bool = True
    enable_proactive_warning: bool = True
    enable_degradation: bool = True
    enable_utility_degradation: bool = True
    enable_hysteresis: bool = True
    enable_recovery: bool = True
    generic_degraded_service_level: float = 0.50

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "name": self.name,
            "enable_risk": self.enable_risk,
            "enable_proactive_warning": self.enable_proactive_warning,
            "enable_degradation": self.enable_degradation,
            "enable_utility_degradation": self.enable_utility_degradation,
            "enable_hysteresis": self.enable_hysteresis,
            "enable_recovery": self.enable_recovery,
            "generic_degraded_service_level": self.generic_degraded_service_level,
        }


def get_ablation_config(code: str) -> AblationConfig:
    """
    Factory function returning the exact AblationConfig for codes A through F.
    """
    c = code.upper().strip()
    if c == "A":
        return AblationConfig(
            code="A",
            name="EDF-VD",
            enable_risk=False,
            enable_proactive_warning=False,
            enable_degradation=False,
            enable_utility_degradation=False,
            enable_hysteresis=False,
            enable_recovery=False,
        )
    elif c == "B":
        return AblationConfig(
            code="B",
            name="EDF-VD + generic degraded LO service",
            enable_risk=False,
            enable_proactive_warning=False,
            enable_degradation=True,
            enable_utility_degradation=False,
            enable_hysteresis=False,
            enable_recovery=False,
            generic_degraded_service_level=0.50,
        )
    elif c == "C":
        return AblationConfig(
            code="C",
            name="EDF-VD + proactive risk",
            enable_risk=True,
            enable_proactive_warning=True,
            enable_degradation=False,
            enable_utility_degradation=False,
            enable_hysteresis=False,
            enable_recovery=False,
        )
    elif c == "D":
        return AblationConfig(
            code="D",
            name="EDF-VD + utility-aware degradation",
            enable_risk=False,
            enable_proactive_warning=False,
            enable_degradation=True,
            enable_utility_degradation=True,
            enable_hysteresis=False,
            enable_recovery=False,
        )
    elif c == "E":
        return AblationConfig(
            code="E",
            name="EDF-VD + proactive risk + degradation",
            enable_risk=True,
            enable_proactive_warning=True,
            enable_degradation=True,
            enable_utility_degradation=True,
            enable_hysteresis=False,
            enable_recovery=False,
        )
    elif c == "F":
        return AblationConfig(
            code="F",
            name="Full AdaptiveGuard",
            enable_risk=True,
            enable_proactive_warning=True,
            enable_degradation=True,
            enable_utility_degradation=True,
            enable_hysteresis=True,
            enable_recovery=True,
        )
    else:
        raise ValueError(f"Unknown ablation configuration code: '{code}'. Expected 'A', 'B', 'C', 'D', 'E', or 'F'.")


ALL_ABLATION_CONFIGS = [get_ablation_config(c) for c in ("A", "B", "C", "D", "E", "F")]
