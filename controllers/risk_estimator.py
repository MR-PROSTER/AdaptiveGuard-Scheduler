"""
Risk Estimator for AdaptiveGuard Discrete-Event Simulator.

Calculates four normalized risk components [0.0, 1.0]:
- R_util    : Short-horizon utilization risk
- R_laxity  : Minimum HI task laxity risk
- R_overrun : Maximum HI task overrun risk
- R_deadline: Most urgent HI task deadline proximity risk

Total Combined Risk:
  R_total = w_util * R_util + w_laxity * R_laxity + w_overrun * R_overrun + w_deadline * R_deadline

Note: Weights and thresholds are project-design parameters, not literature-derived constants.
"""

from dataclasses import dataclass
from typing import List
from controllers.runtime_monitor import JobState
from simulator.task import Criticality


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp value to range [min_val, max_val]."""
    return max(min_val, min(max_val, value))


@dataclass
class RiskMetrics:
    """
    Calculated risk components and total risk snapshot at timestamp t.
    """

    timestamp: float
    r_util: float
    r_laxity: float
    r_overrun: float
    r_deadline: float
    r_total: float
    event_trigger: str = ""


class RiskEstimator:
    """
    Risk Estimator engine.

    Attributes:
        w_util (float): Weight for utilization risk (default: 0.30)
        w_laxity (float): Weight for laxity risk (default: 0.30)
        w_overrun (float): Weight for overrun risk (default: 0.25)
        w_deadline (float): Weight for deadline risk (default: 0.15)
        l_safe (float): Safe laxity threshold in ms (default: 5.0)
        t_safe (float): Safe time-to-deadline threshold in ms (default: 5.0)
    """

    def __init__(
        self,
        w_util: float = 0.30,
        w_laxity: float = 0.30,
        w_overrun: float = 0.25,
        w_deadline: float = 0.15,
        l_safe: float = 5.0,
        t_safe: float = 5.0,
    ) -> None:
        self.w_util: float = w_util
        self.w_laxity: float = w_laxity
        self.w_overrun: float = w_overrun
        self.w_deadline: float = w_deadline
        self.l_safe: float = l_safe
        self.t_safe: float = t_safe

    def calculate_r_util(
        self,
        job_states: List[JobState],
        current_time: float,
        cpu_speed: float = 1.0,
    ) -> float:
        """
        Calculate Utilization Risk (R_util).

        Calculation Method for current_demand:
          For all active jobs, current_demand is calculated as the sum of remaining execution times
          divided by the time horizon to the maximum active absolute deadline (d_max - t).
          Formula:
            current_demand_rate = sum(remaining_execution) / max(eps, d_max - current_time)
            available_capacity = cpu_speed
            R_util = clamp(current_demand_rate / available_capacity, 0, 1)

          If no active jobs are present, R_util = 0.0.
        """
        if not job_states:
            return 0.0

        total_remaining = sum(js.remaining_execution for js in job_states)
        if total_remaining <= 0:
            return 0.0

        max_deadline = max(js.absolute_deadline for js in job_states)
        horizon = max(1e-6, max_deadline - current_time)

        current_demand_rate = total_remaining / horizon
        available_capacity = cpu_speed

        return clamp(current_demand_rate / available_capacity, 0.0, 1.0)

    def calculate_r_laxity(self, job_states: List[JobState]) -> float:
        """
        Calculate Laxity Risk (R_laxity) based on minimum laxity among active HI jobs.

        Formula:
            If min_laxity <= 0: R_laxity = 1
            Elif min_laxity >= L_safe (5ms): R_laxity = 0
            Else: R_laxity = 1 - min_laxity / L_safe
        """
        hi_states = [js for js in job_states if js.criticality == Criticality.HI]
        if not hi_states:
            return 0.0

        min_laxity = min(js.laxity for js in hi_states)
        if min_laxity <= 0.0:
            return 1.0
        elif min_laxity >= self.l_safe:
            return 0.0
        else:
            return 1.0 - (min_laxity / self.l_safe)

    def calculate_r_overrun(self, job_states: List[JobState]) -> float:
        """
        Calculate Overrun Risk (R_overrun) as maximum overrun risk among active HI jobs.

        Formula:
            For each active HI job:
              risk = 1.0 if execution_received >= C_LO and not completed else 0.0
            R_overrun = max(risk)
        """
        hi_states = [js for js in job_states if js.criticality == Criticality.HI]
        if not hi_states:
            return 0.0

        overrun_risks = [1.0 if js.overrun_status else 0.0 for js in hi_states]
        return max(overrun_risks) if overrun_risks else 0.0

    def calculate_r_deadline(self, job_states: List[JobState]) -> float:
        """
        Calculate Deadline Risk (R_deadline) for the most urgent HI job.

        Formula:
            For the most urgent HI job (min time_to_deadline):
              If time_to_deadline <= 0: R_deadline = 1
              Elif time_to_deadline >= T_safe (5ms): R_deadline = 0
              Else: R_deadline = 1 - time_to_deadline / T_safe
        """
        hi_states = [js for js in job_states if js.criticality == Criticality.HI]
        if not hi_states:
            return 0.0

        min_time_to_deadline = min(js.time_to_deadline for js in hi_states)
        if min_time_to_deadline <= 0.0:
            return 1.0
        elif min_time_to_deadline >= self.t_safe:
            return 0.0
        else:
            return 1.0 - (min_time_to_deadline / self.t_safe)

    def calculate_total_risk(
        self, r_util: float, r_laxity: float, r_overrun: float, r_deadline: float
    ) -> float:
        """
        Calculate combined total risk:
            R_total = w_util * R_util + w_laxity * R_laxity + w_overrun * R_overrun + w_deadline * R_deadline
        """
        total = (
            self.w_util * r_util
            + self.w_laxity * r_laxity
            + self.w_overrun * r_overrun
            + self.w_deadline * r_deadline
        )
        return clamp(total, 0.0, 1.0)

    def evaluate(
        self,
        job_states: List[JobState],
        current_time: float,
        cpu_speed: float = 1.0,
        event_trigger: str = "",
    ) -> RiskMetrics:
        """
        Evaluate full risk profile at current_time.
        """
        r_util = self.calculate_r_util(job_states, current_time, cpu_speed)
        r_laxity = self.calculate_r_laxity(job_states)
        r_overrun = self.calculate_r_overrun(job_states)
        r_deadline = self.calculate_r_deadline(job_states)
        r_total = self.calculate_total_risk(r_util, r_laxity, r_overrun, r_deadline)

        return RiskMetrics(
            timestamp=current_time,
            r_util=r_util,
            r_laxity=r_laxity,
            r_overrun=r_overrun,
            r_deadline=r_deadline,
            r_total=r_total,
            event_trigger=event_trigger,
        )
