"""Workloads package for AdaptiveGuard discrete-event simulator."""
from workloads.fixed_workload import (
    WORKLOAD_NAME,
    ExecutionScenario,
    get_fixed_workload,
    get_stress_20ms_workload,
    calculate_hi_lo_utilization,
    calculate_lo_utilization,
    calculate_normal_utilization,
    calculate_worst_case_utilization,
    print_workload_utilization,
    get_job_execution_requirement,
)

__all__ = [
    "WORKLOAD_NAME",
    "ExecutionScenario",
    "get_fixed_workload",
    "get_stress_20ms_workload",
    "calculate_hi_lo_utilization",
    "calculate_lo_utilization",
    "calculate_normal_utilization",
    "calculate_worst_case_utilization",
    "print_workload_utilization",
    "get_job_execution_requirement",
]
