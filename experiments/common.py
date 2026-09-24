"""
Common CSV Exporter and Utilities for AdaptiveGuard Experiments.
"""

from pathlib import Path
import csv
from typing import List, Dict, Any

COMMON_FIELDNAMES = [
    "experiment_type",
    "ablation_code",
    "sensitivity_param",
    "monitor_interval",
    "scheduler",
    "num_tasks",
    "target_utilization",
    "hi_ratio",
    "seed",
    "U_LO",
    "U_HI_LO",
    "U_HI_HI",
    "U_total_LO",
    "U_total_HI",
    "hi_missed_count",
    "hi_miss_ratio",
    "lo_completion_ratio",
    "LO_utility",
    "maximum_possible_LO_utility",
    "LO_utility_ratio",
    "mode_switches",
    "total_overhead",
    "overhead_percentage",
]


def save_results_to_csv(
    results: List[Dict[str, Any]],
    output_csv: str = "results/raw/simulation_results.csv",
    mode: str = "a",
) -> None:
    """
    Save simulation result rows using standardized column schema.
    """
    if not results:
        return

    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    file_exists = out_path.exists() and mode == "a"

    normalized_results: List[Dict[str, Any]] = []
    for row in results:
        norm_row = {field: row.get(field, "") for field in COMMON_FIELDNAMES}
        normalized_results.append(norm_row)

    with open(out_path, mode=mode, newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COMMON_FIELDNAMES)
        if not file_exists:
            writer.writeheader()
        writer.writerows(normalized_results)
