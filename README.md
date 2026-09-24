# AdaptiveGuard: Proactive and Graceful Mixed-Criticality Real-Time Simulator

[![Python Version](https://img.shields.io/badge/python-3.14%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/pytest-57%20passed-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**AdaptiveGuard** is a research-grade Python discrete-event simulator for **Mixed-Criticality (MC) Real-Time Systems**. It integrates Earliest Deadline First with Virtual Deadlines (**EDF-VD**), proactive runtime risk estimation, hysteresis-protected multi-state criticality control (`LO` $\leftrightarrow$ `WARNING` $\leftrightarrow$ `HI` $\to$ `RECOVERY`), utility-density task degradation, and gradual LO-task service restoration.

---

## 1. System Architecture & Control Loop

AdaptiveGuard unifies proactive monitoring, risk estimation, and dynamic LO-task degradation into a closed-loop control cycle:

```
              ┌─────────────────────────────────────────────────────────┐
              │                     Job Execution                       │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │            Runtime Monitor (Laxity & Overrun)           │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │        Proactive Risk Estimator (R_total score)         │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │ Mode Controller (LO <-> WARNING <-> HI -> RECOVERY)      │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │ Degradation / Recovery Controller (Utility Density U_i/C)│
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │         EDF-VD Scheduler (Virtual Deadlines d'_i)       │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           ▼
              ┌─────────────────────────────────────────────────────────┐
              │                       CPU Core                          │
              └────────────────────────────┬────────────────────────────┘
                                           │
                                           └────( repeat control loop )
```

### Key Components

- **EDF-VD Virtual Deadlines**: HI-criticality tasks use virtual deadlines ($d'_i = r_i + x \cdot (D_i - r_i)$ with $x = \frac{U_{\text{HI\_LO}}}{1 - U_{\text{LO}}}$) during `LO` and `WARNING` modes, reverting to actual deadlines in `HI` or `RECOVERY` modes.
- **Runtime Monitor**: Computes real-time execution received, remaining time, time-to-deadline, laxity ($L_i(t) = D_i - t - R_i(t)$), and overrun status at discrete sampling checkpoints ($0.5\text{ ms}$ default).
- **Multi-Factor Risk Estimator**: Calculates a normalized combined risk score $R_{\text{total}} \in [0.0, 1.0]$:
  $$R_{\text{total}} = w_{\text{util}} R_{\text{util}} + w_{\text{laxity}} R_{\text{laxity}} + w_{\text{overrun}} R_{\text{overrun}} + w_{\text{deadline}} R_{\text{deadline}}$$
- **Mode Controller with Hysteresis**: Manages criticality transitions (`LO` $\leftrightarrow$ `WARNING` $\leftrightarrow$ `HI` $\to$ `RECOVERY`). Entering `RECOVERY` requires total risk $R_{\text{total}} \le 0.40$ continuously for a hold time ($t_{\text{hold}} = 5.0\text{ ms}$).
- **Utility-Aware LO Degradation**: Ranks LO tasks descending by utility density ($\text{utility\_density} = U_i / C_{\text{LO}, i}$). Reduces service of lower utility-density tasks first ($1.00 \to 0.75 \to 0.50 \to 0.25 \to 0.00$) in `WARNING` mode while protecting HI tasks ($1.00$).
- **Gradual Recovery Controller**: Restores LO tasks step-by-step ($0.00 \to 0.25 \to 0.50 \to 0.75 \to 1.00$) in `RECOVERY` mode, restoring higher utility-density tasks first.
- **Simulated Overhead Accounting**: Models realistic latencies ($0.01\text{ ms}$ per scheduling decision, $0.005\text{ ms}$ per risk calculation, $0.01\text{ ms}$ per mode switch).

---

## 2. Project Directory Structure

```
AdaptiveGuard-Scheduler/
├── README.md                           # Comprehensive documentation & user guide
├── main.py                             # Fixed workload demo & 7-scheduler matrix runner
├── run_experiments.py                  # Full experiment orchestrator & report generator
├── config/
│   └── default_config.py               # System & overhead configuration defaults
├── controllers/
│   ├── runtime_monitor.py              # Active job laxity & execution monitor
│   ├── risk_estimator.py               # Multi-component risk scoring engine
│   ├── mode_controller.py              # System mode state machine with hysteresis
│   ├── degradation_controller.py       # Utility-density LO degradation controller
│   └── recovery_controller.py          # Step-by-step gradual recovery controller
├── schedulers/
│   ├── base_scheduler.py               # Abstract scheduler interface
│   ├── edf.py                          # Standard Earliest Deadline First
│   ├── edf_vd.py                       # EDF with Virtual Deadlines (Baruah et al.)
│   ├── classical_mc.py                 # Classical Reactive MC baseline
│   ├── degraded_edf_vd.py              # EDF-VD + Degraded LO Service baseline
│   ├── flexible_mc.py                  # Flexible MC baseline
│   ├── proactive_risk_mc.py            # Proactive Risk / Mode Change baseline
│   └── adaptive_guard.py               # Integrated AdaptiveGuard Scheduler
├── simulator/
│   ├── task.py                         # Task data model & criticality validation
│   ├── job.py                          # Job instance model & execution state
│   ├── event.py                        # Discrete event data structures
│   ├── event_queue.py                  # Min-heap priority queue
│   ├── cpu.py                          # Single CPU execution engine & preemption
│   ├── clock.py                        # Microsecond simulation clock
│   └── simulation.py                   # Discrete-event simulation orchestrator
├── workloads/
│   ├── fixed_workload.py               # stress_20ms benchmark workload
│   ├── uunifast.py                     # UUniFast utilization distribution generator
│   └── generator.py                    # Synthetic taskset generator
├── metrics/
│   ├── deadline_metrics.py             # Miss ratios & response times
│   ├── utility_metrics.py              # Utility values & preservation ratios
│   ├── overhead_metrics.py             # Microsecond overhead tracking
│   └── mode_metrics.py                 # Mode switch statistics
├── visualization/
│   ├── timeline.py                     # stress_20ms dynamic timeline plot
│   ├── utilization_plot.py            # Metrics vs target utilization plots
│   ├── utility_plot.py                 # Monitoring interval & utility plots
│   ├── risk_plot.py                    # Risk score & mode over time plots
│   └── comparison.py                   # Recovery time & ablation study plots
├── experiments/
│   ├── common.py                       # Standardized CSV exporter schema
│   ├── run_baselines.py                # Baseline schedulers experiment runner
│   ├── run_adaptive.py                 # AdaptiveGuard experiment runner
│   ├── run_ablation.py                 # Ablation study runner (Components A-F)
│   ├── run_sensitivity.py              # Weight & threshold sensitivity runner
│   └── run_monitoring_experiment.py    # Sampling interval sensitivity runner
└── tests/                              # 57 unit tests (100% passing)
```

---

## 3. Installation & Setup

1. **Activate Virtual Environment**:
   ```bash
   source ../venv/bin/activate
   ```

2. **Install Dependencies** (if needed):
   ```bash
   pip install pytest matplotlib pandas numpy tabulate
   ```

---

## 4. How to Run

### A. Run Fixed Benchmark Workload Demonstration (`stress_20ms`)
Executes all 7 schedulers across 4 scenarios (`NORMAL`, `H1_OVERRUN`, `BOTH_OVERRUN`, `RECOVERY`) under both **Idealized (Overhead-Free)** and **Overhead-Enabled** modes:

```bash
python main.py
```

### B. Run Full Unit Test Suite (57 Tests)
Executes all unit tests verifying task/job data models, schedulers, controllers, mode transitions, degradation rules, gradual recovery, and overhead accounting:

```bash
pytest
```

### C. Run Research Experiment Pipeline & Build Report
Runs the complete experiment suite (Baselines, AdaptiveGuard, Ablation A-F, Sensitivity Analysis, and Monitoring Sampling Interval), outputs raw CSV data, produces 13 visualization plots, and compiles `results/experiment_report.md`:

```bash
python run_experiments.py
```

For the full 1000-taskset research evaluation:
```bash
python run_experiments.py --full
```

### D. Run Individual Experiment Scripts

- **Baseline Schedulers Experiment**:
  ```bash
  python -c "from experiments.run_baselines import run_baselines_experiment; run_baselines_experiment(num_tasksets=20, duration=5000.0)"
  ```

- **AdaptiveGuard Experiments**:
  ```bash
  python -c "from experiments.run_adaptive import run_adaptive_experiment; run_adaptive_experiment(num_tasksets=20, duration=5000.0)"
  ```

- **Ablation Study (Components A through F)**:
  ```bash
  python -c "from experiments.run_ablation import run_ablation_experiment; run_ablation_experiment(num_tasksets=20, duration=5000.0)"
  ```

- **Sensitivity Analysis (Risk Weights & Thresholds)**:
  ```bash
  python -c "from experiments.run_sensitivity import run_sensitivity_experiments; run_sensitivity_experiments(num_tasksets=15, duration=5000.0)"
  ```

- **Monitoring Sampling Interval Analysis**:
  ```bash
  python -c "from experiments.run_monitoring_experiment import run_monitoring_experiment; run_monitoring_experiment(num_tasksets=15, duration=5000.0)"
  ```

- **Re-generate Visualization Plots**:
  ```bash
  python -c "import pandas as pd; from visualization import *; df=pd.read_csv('../results/raw/simulation_results.csv'); generate_utilization_plots(df); generate_utility_and_monitoring_plots(df); generate_ablation_and_recovery_plots(df)"
  ```

---

## 5. Results & Visualization Artifacts

All experiment outputs are generated into `../results/`:

### A. Raw Data & Research Report
- `../results/raw/simulation_results.csv`: Complete empirical simulation results dataset.
- `../results/experiment_report.md`: Full markdown research report with system model definitions, statistical parameter tables, and component analysis.

### B. Summary Performance Matrix (Overhead-Enabled Synthetic Evaluation)

| Scheduler | HI Miss Ratio | LO Completion Ratio | LO Utility Ratio | Mode Switches | Overhead (%) |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **EDF** | 0.2395 | 0.7973 | 0.7891 | 0 | 0.00% |
| **EDF-VD** | 0.1269 | 0.0027 | 0.0021 | 1 | 0.00% |
| **Classical Reactive MC** | 0.1269 | 0.0037 | 0.0030 | 1 | 0.00% |
| **EDF-VD + Degraded LO Service** | 0.1872 | 0.8725 | 0.8654 | 1 | 0.00% |
| **Flexible MC** | 0.2404 | 0.7973 | 0.7891 | 4.67 | 0.00% |
| **Proactive Risk / Mode Change** | 0.1291 | 0.4108 | 0.3978 | 19.19 | 6.90% |
| **AdaptiveGuard (Full)** | **0.2756** | **0.7519** | **0.7319** | **18.06** | **7.15%** |

### C. Generated Chart Artifacts (`../results/plots/`)
1. `1_hi_miss_ratio_vs_utilization.png`: HI Deadline Miss Ratio vs Target Utilization.
2. `2_lo_utility_preservation_vs_utilization.png`: LO Utility Preservation Ratio vs Target Utilization.
3. `3_lo_completion_ratio_vs_utilization.png`: LO Completion Ratio vs Target Utilization.
4. `4_mode_switches_vs_utilization.png`: Mode Switches vs Target Utilization.
5. `5_overhead_vs_utilization.png`: Simulated CPU Overhead vs Target Utilization.
6. `6_recovery_time_comparison.png`: System Recovery Duration across Schedulers.
7. `7_risk_score_over_time.png`: Dynamic Risk Score Trajectory ($R_{\text{total}}$).
8. `8_mode_over_time.png`: System Criticality Mode Trajectory (`LO`, `WARNING`, `HI`, `RECOVERY`).
9. `9_lo_service_levels_over_time.png`: Per-Task Service Level Dynamics ($1.00 \to 0.00$).
10. `10_monitoring_interval_vs_overhead.png`: Monitoring Interval vs CPU Overhead.
11. `11_monitoring_interval_vs_lo_utility.png`: Monitoring Interval vs LO Utility.
12. `12_ablation_study.png`: Ablation Study Performance Breakdown (Components A-F).
13. `stress_20ms_timeline.png`: Benchmark execution timeline diagram.

---

## 6. Schedulers Evaluated

1. **EDF**: Standard Earliest Deadline First without criticality awareness.
2. **EDF-VD**: Earliest Deadline First with Virtual Deadlines ($x = U_{\text{HI\_LO}} / (1 - U_{\text{LO}})$).
3. **Classical Reactive MC**: Mode switch triggered reactively when a HI task exceeds $C_{\text{LO}}$; drops LO tasks in HI mode.
4. **EDF-VD + Degraded LO Service**: Maintains LO tasks at a reduced service level ($0.50 \times C_{\text{LO}}$) in HI mode.
5. **Flexible MC**: Per-task independent escalation upon overrun without global mode switch.
6. **Proactive Risk / Mode Change**: Proactive mode controller using risk estimation, without utility-density ranking.
7. **AdaptiveGuard**: Full integrated framework combining proactive risk estimation, hysteresis-protected `WARNING` and `RECOVERY` states, utility-density task degradation, and gradual LO service restoration.

---

## 7. License

This project is licensed under the MIT License - see the `LICENSE` file for details.
