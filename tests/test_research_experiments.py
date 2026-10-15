"""
Unit tests for the Reproducible Research Experiments Framework.
"""

from pathlib import Path
import tempfile
import pytest

from experiments.research_experiments import (
    ResearchExperimentConfig,
    create_timestamped_directory,
    create_schedulers_for_taskset,
    save_raw_results,
    generate_summary_tables,
    RESEARCH_METRICS_FIELDNAMES,
)
from workloads.generator import TasksetGenerator


def test_research_experiment_config_defaults():
    """Verify default research experiment configuration conforms to specification."""
    cfg = ResearchExperimentConfig()
    assert cfg.task_counts == [5, 10, 20, 30, 50]
    assert len(cfg.target_utilizations) == 12
    assert cfg.target_utilizations[0] == 0.40
    assert cfg.target_utilizations[-1] == 1.50
    assert cfg.hi_ratios == [0.20, 0.40, 0.60]
    assert cfg.duration == 5000.0
    assert cfg.warmup_time == 500.0
    assert cfg.num_tasksets == 10
    assert cfg.c_hi_factor == 2.5


def test_timestamped_directory_creation():
    """Verify unique timestamped directories are created."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        dir1 = create_timestamped_directory(tmp_dir)
        assert dir1.exists()
        assert dir1.is_dir()
        assert dir1.name.startswith("experiments_")


def test_create_schedulers_for_taskset():
    """Verify all 6 research schedulers are instantiated."""
    gen = TasksetGenerator()
    tasks = gen.generate_taskset(num_tasks=5, target_utilization=0.6, hi_ratio=0.4, seed=99)
    schedulers = create_schedulers_for_taskset(tasks)
    assert len(schedulers) == 6
    names = [s.name for s in schedulers]
    assert "EDF" in names
    assert "EDF-VD" in names
    assert "Classical Reactive MC" in names
    assert "EDF-VD + Degraded LO Service" in names
    assert "Flexible MC" in names
    assert "AdaptiveGuard" in names


def test_metrics_fieldnames_completeness():
    """Verify all 13 research metrics are present in fieldnames."""
    required = [
        "hi_miss_ratio",
        "lo_completion_ratio",
        "lo_utility_ratio",
        "average_response_time",
        "worst_response_time",
        "cpu_utilization",
        "mode_switches",
        "warning_duration",
        "hi_duration",
        "recovery_duration",
        "recovery_time",
        "total_overhead",
        "overhead_percentage",
    ]
    for m in required:
        assert m in RESEARCH_METRICS_FIELDNAMES, f"Metric '{m}' missing from fieldnames!"


def test_summary_aggregation():
    """Verify summary table generation aggregates metrics correctly."""
    mock_results = [
        {
            "scheduler": "AdaptiveGuard",
            "target_utilization": 0.8,
            "hi_miss_ratio": 0.0,
            "lo_completion_ratio": 0.9,
            "lo_utility_ratio": 0.95,
            "average_response_time": 12.0,
            "worst_response_time": 25.0,
            "cpu_utilization": 0.85,
            "mode_switches": 4,
            "warning_duration": 10.0,
            "hi_duration": 20.0,
            "recovery_duration": 5.0,
            "recovery_time": 5.0,
            "total_overhead": 0.5,
            "overhead_percentage": 0.01,
        },
        {
            "scheduler": "AdaptiveGuard",
            "target_utilization": 0.8,
            "hi_miss_ratio": 0.0,
            "lo_completion_ratio": 0.8,
            "lo_utility_ratio": 0.85,
            "average_response_time": 14.0,
            "worst_response_time": 30.0,
            "cpu_utilization": 0.85,
            "mode_switches": 6,
            "warning_duration": 12.0,
            "hi_duration": 22.0,
            "recovery_duration": 6.0,
            "recovery_time": 6.0,
            "total_overhead": 0.6,
            "overhead_percentage": 0.012,
        },
    ]
    summaries = generate_summary_tables(mock_results)
    by_sched = summaries["by_scheduler"]
    assert len(by_sched) == 1
    ag = by_sched[0]
    assert ag["scheduler"] == "AdaptiveGuard"
    assert ag["runs_count"] == 2
    assert ag["lo_utility_ratio"] == pytest.approx(0.90)
    assert ag["worst_response_time"] == 30.0
