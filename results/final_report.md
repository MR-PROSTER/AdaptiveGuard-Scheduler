# AdaptiveGuard: Adaptive Mixed-Criticality Real-Time Scheduling Architecture

---

## 1. Problem Statement

Modern embedded real-time systems—such as autonomous vehicles, avionics mission computers, and robotic control units—increasingly integrate tasks of differing criticality levels onto shared multicore computing platforms. These systems are governed by the **Mixed-Criticality (MC)** paradigm:
1. **High-Criticality (HI)** tasks control safety-critical operations (e.g., flight control, obstacle braking, vehicle stabilization) and must guarantee zero deadline misses even under worst-case transient disturbances.
2. **Low-Criticality (LO)** tasks manage mission-critical or best-effort operations (e.g., telemetry streaming, map updates, sensor logging, cabin monitoring) whose deadlines are secondary to safety, but whose execution delivers vital system utility.

The central challenge in mixed-criticality scheduling is the **safety-utility trade-off**:
* Traditional certification frameworks (e.g., Vestal's model) handle overruns by **sacrificing all LO-criticality tasks unconditionally** the moment any HI task exceeds its nominal execution budget ($C(\text{LO})$).
* While this extreme response protects HI tasks, it causes a catastrophic drop to **zero LO task utility**, starvation of mission tasks, and severe degradation of overall mission performance.
* Conversely, standard real-time schedulers like Earliest Deadline First (EDF) preserve LO utility during normal loads, but collapse during system overruns, leading to uncontained HI deadline misses.

The goal of this research is to evaluate **AdaptiveGuard**, an adaptive, risk-aware mixed-criticality scheduling framework designed to proactively anticipate overload, modulate LO service levels using a knapsack-based utility optimization, prevent unnecessary mode oscillations via hysteresis, and safely recover to nominal execution.

---

## 2. Research Motivation

Conventional mixed-criticality approaches suffer from three foundational design flaws:
1. **Purely Reactive Mode Switching**: Baseline MC schedulers (e.g., EDF-VD, Classical MC) switch modes only *after* a HI task overruns its nominal execution time ($t_{\text{exec}} > C_i(\text{LO})$). By waiting until a physical overrun has already occurred, the scheduler has zero lead time to shed load smoothly, forcing immediate task termination.
2. **Binary All-or-Nothing LO Service**: Upon switching to HI mode, LO tasks are either discarded entirely or uniformly degraded to an arbitrary static fraction. This ignores task importance and the concave utility-density characteristics of realistic tasks.
3. **Irreversible or Unstable Recovery**: Classical schedulers never return to LO mode, permanently forfeiting LO utility for the remainder of the mission. Naive recovery mechanisms suffer from high-frequency mode oscillations ("chattering"), causing significant mode transition overhead and CPU thrashing.

AdaptiveGuard was conceived to address these limitations through:
* Proactive multi-factor risk estimation.
* An intermediate `WARNING` mode providing early load shedding.
* Utility-aware knapsack degradation of LO tasks.
* Dual-threshold hysteresis and gradual step recovery.

This report evaluates whether AdaptiveGuard delivers on its theoretical promises under strict, empirical discrete-event simulation with non-zero computational overhead.

---

## 3. Existing Approaches

### 3.1 Earliest Deadline First (EDF)
* **Principle**: Jobs are dynamically prioritized according to their absolute deadlines ($d_{i,k}$). At each scheduling point, the job with the earliest deadline is dispatched.
* **Failure Mode in Mixed-Criticality**: EDF is criticality-agnostic. When transient overloads occur, an impending LO job with an early deadline will preempt a critical HI job, causing severe HI deadline misses (up to 70.0% miss ratio in our experiments).

### 3.2 Earliest Deadline First with Virtual Deadlines (EDF-VD)
* **Principle**: Proposed by Baruah et al., EDF-VD accelerates HI tasks in LO mode by scaling their relative deadlines using a virtual deadline factor $x \in (0, 1]$:
  $$D_i^V = x \cdot D_i$$
  In LO mode, jobs are scheduled using virtual deadlines for HI tasks and physical deadlines for LO tasks.
* **Failure Mode**: When any HI job executes beyond $C_i(\text{LO})$ without completing, the system switches to HI mode and aborts all LO tasks.

### 3.3 Classical Reactive Mixed-Criticality Scheduling
* **Principle**: Generalization of Vestal's model where tasks run under standard deadlines. The moment a single HI job exceeds $C_i(\text{LO})$, all active and future LO jobs are dropped permanently.
* **Limitation**: Completely zero utility preservation ($0.0\%$) and zero recovery capability.

### 3.4 EDF-VD with Degraded LO Service
* **Principle**: Instead of dropping all LO tasks, every LO task's execution budget is scaled down uniformly by a fixed factor (e.g., $\theta_i = 0.50$).
* **Limitation**: Blindly scales all LO tasks equally regardless of their utility contribution or execution density, causing substantial utility loss for high-value tasks while keeping low-value tasks alive.

### 3.5 Flexible Mixed-Criticality Scheduling
* **Principle**: Dynamically adjusts LO task execution parameters or skips selected jobs based on queue pressure.
* **Limitation**: Without explicit proactive risk modeling and virtual deadline scaling, Flexible MC struggles to prevent HI deadline misses under severe overutilization ($U > 1.0$), behaving similarly to unconstrained EDF.

---

## 4. Proposed AdaptiveGuard Architecture

AdaptiveGuard integrates four modular control layers operating synchronously with the discrete-event simulation engine:

```
+-----------------------------------------------------------------------+
|                             AdaptiveGuard                             |
|                                                                       |
|  +--------------------+     +-------------------+     +------------+  |
|  |  Runtime Monitor   | --> |  Risk Estimator   | --> |    Mode    |  |
|  |  (Periodic del_t)  |     |  Composite R(t)   |     | Controller |  |
|  +--------------------+     +-------------------+     +------------+  |
|                                                             |         |
|                                                             v         |
|  +--------------------+     +-------------------+     +------------+  |
|  |    CPU Dispatch    | <-- |      EDF-VD       | <-- | Degradation|  |
|  |  (Job Execution)   |     | Virtual Deadlines |     | Controller |  |
|  +--------------------+     +-------------------+     +------------+  |
+-----------------------------------------------------------------------+
```

### 4.1 Runtime Monitor
* Intercepts the CPU at discrete checkpoints $\Delta t$ (default $0.5$ ms) and at scheduling events (job release, completion, preemption).
* Samples instantaneous queue state, executing job progress, remaining capacity, and deadline slack.

### 4.2 Composite Risk Estimator
* Computes an instantaneous multi-factor risk score $R(t) \in [0, 1]$:
  $$R(t) = w_{\text{util}} \cdot r_{\text{util}}(t) + w_{\text{laxity}} \cdot r_{\text{laxity}}(t) + w_{\text{overrun}} \cdot r_{\text{overrun}}(t) + w_{\text{deadline}} \cdot r_{\text{deadline}}(t)$$
* Default normalized weights: $w_{\text{util}} = 0.30, w_{\text{laxity}} = 0.30, w_{\text{overrun}} = 0.25, w_{\text{deadline}} = 0.15$.

### 4.3 Operational Modes
AdaptiveGuard defines four discrete operational modes:
1. **`LO` Mode**: Normal execution. Full LO service levels ($\theta_i = 1.0$). HI tasks use virtual deadlines $D_i^V = x \cdot D_i$.
2. **`WARNING` Mode**: Proactive alert state triggered when $R(t) \ge R_{\text{warn}}$ ($0.35$). The system preemptively degrades LO service levels to shed load before physical overruns occur.
3. **`HI` Mode**: Triggered when $R(t) \ge R_{\text{hi}}$ ($0.70$) or when an actual HI execution overrun occurs ($t_{\text{exec}} > C_i(\text{LO})$). Strict safety prioritization; LO tasks are degraded to minimal allocations or paused.
4. **`RECOVERY` Mode**: Entered when risk subsides below recovery thresholds for a sustained stabilization window. Restores LO task service levels incrementally.

### 4.4 Utility-Aware Degradation Controller
* Formulates load shedding as a **0/1 or Bounded Knapsack Problem** based on task utility density $\rho_i = \frac{U_i}{C_i(\text{LO})}$.
* Tasks are prioritized such that high-density LO tasks retain full or near-full service levels, while low-density tasks are degraded first.

### 4.5 Dual-Threshold Hysteresis and Gradual Recovery
* Prevents mode chattering by requiring risk to drop below a lower threshold ($R(t) < R_{\text{rec}} = 0.20$) and remain stable for a hold duration before entering `RECOVERY`.
* Reinstates LO service in gradual steps ($\Delta \theta = 0.25$ per recovery interval) rather than instantaneous jumps.

---

## 5. Mathematical Model

### 5.1 System and Task Model
Let $\tau = \{\tau_1, \tau_2, \dots, \tau_n\}$ be a set of $n$ periodic/sporadic mixed-criticality tasks. Each task $\tau_i$ is characterized by:
$$\tau_i = (T_i, D_i, \chi_i, C_i(\text{LO}), C_i(\text{HI}), U_i)$$
where:
* $T_i$: Minimum inter-arrival time (period).
* $D_i$: Relative deadline (constrained deadline: $D_i \le T_i$; implicit deadline: $D_i = T_i$).
* $\chi_i \in \{\text{LO}, \text{HI}\}$: Criticality level.
* $C_i(\text{LO})$: Nominal worst-case execution time under LO mode.
* $C_i(\text{HI})$: Conservative worst-case execution time under HI mode ($C_i(\text{HI}) \ge C_i(\text{LO})$ if $\chi_i = \text{HI}$; $C_i(\text{HI}) = C_i(\text{LO})$ if $\chi_i = \text{LO}$).
* $U_i$: Static utility weight delivered by each successfully completed job of $\tau_i$.

### 5.2 Utilization Bounds
Task utilization in nominal and overrun modes:
$$u_i(\text{LO}) = \frac{C_i(\text{LO})}{T_i}, \quad u_i(\text{HI}) = \frac{C_i(\text{HI})}{T_i}$$

Aggregated utilization components:
$$U_{\text{LO}}^{\text{LO}} = \sum_{\tau_i \in \text{LO}} \frac{C_i(\text{LO})}{T_i}, \quad U_{\text{HI}}^{\text{LO}} = \sum_{\tau_i \in \text{HI}} \frac{C_i(\text{LO})}{T_i}, \quad U_{\text{HI}}^{\text{HI}} = \sum_{\tau_i \in \text{HI}} \frac{C_i(\text{HI})}{T_i}$$

Total nominal utilization $U_{\text{total}}^{\text{LO}} = U_{\text{LO}}^{\text{LO}} + U_{\text{HI}}^{\text{LO}}$. Total peak utilization $U_{\text{total}}^{\text{HI}} = U_{\text{LO}}^{\text{LO}} + U_{\text{HI}}^{\text{HI}}$.

### 5.3 Virtual Deadline Factor
For schedulability under EDF-VD, the virtual deadline scaling factor $x$ is computed as:
$$x = \frac{U_{\text{HI}}^{\text{LO}}}{1 - U_{\text{LO}}^{\text{LO}}}$$
When $U_{\text{total}}^{\text{LO}} \le 1$ and $x \cdot U_{\text{LO}}^{\text{LO}} + U_{\text{HI}}^{\text{HI}} \le 1$, schedulability is guaranteed. The virtual deadline of job $J_{i,k}$ released at $r_{i,k}$ is:
$$d_{i,k}^V = r_{i,k} + x \cdot D_i$$

### 5.4 Laxity and Risk Components
For any active job $J_{i,k}$ at current time $t$:
* Remaining execution requirement: $c_{i,k}^{\text{rem}}(t) = C_{i,k}^{\text{actual}} - e_{i,k}(t)$
* Absolute deadline: $d_{i,k}$
* Instantaneous laxity: $L_{i,k}(t) = d_{i,k} - t - c_{i,k}^{\text{rem}}(t)$

The four risk sub-components are defined as:
1. **Utilization Pressure**:
   $$r_{\text{util}}(t) = \min\left(1.0, \frac{\sum_{J_{j} \in \mathcal{Q}(t)} c_j^{\text{rem}}(t)}{\max_{J_j \in \mathcal{Q}(t)}(d_j) - t + \epsilon}\right)$$
2. **Critical Laxity Deficit**:
   $$r_{\text{laxity}}(t) = \max_{\tau_i \in \text{HI}, J_{i,k} \in \mathcal{Q}(t)} \left(1.0 - \max\left(0.0, \frac{L_{i,k}(t)}{D_i}\right)\right)$$
3. **Execution Overrun Proximity**:
   $$r_{\text{overrun}}(t) = \max_{\tau_i \in \text{HI}, J_{i,k} \in \mathcal{Q}(t)} \left(\frac{e_{i,k}(t)}{C_i(\text{LO})}\right)$$
4. **Deadline Proximity**:
   $$r_{\text{deadline}}(t) = \max_{\tau_i \in \text{HI}, J_{i,k} \in \mathcal{Q}(t)} \left(1.0 - \frac{d_{i,k} - t}{D_i}\right)$$

Composite risk:
$$R(t) = \sum_{k \in \{\text{util}, \text{laxity}, \text{overrun}, \text{deadline}\}} w_k \cdot r_k(t), \quad \sum w_k = 1.0$$

### 5.5 Utility Density and Knapsack Degradation
For each LO task $\tau_i$, utility density is:
$$\rho_i = \frac{U_i}{C_i(\text{LO})}$$
Given target capacity reduction $\Delta U_{\text{target}}$ demanded by current mode:
$$\max_{\{\theta_i \in [\theta_{\min}, 1.0]\}} \sum_{\tau_i \in \text{LO}} \theta_i \cdot U_i \quad \text{s.t.} \quad \sum_{\tau_i \in \text{LO}} \theta_i \cdot u_i(\text{LO}) \le U_{\text{budget}}$$

### 5.6 Metric Definitions
* **HI Deadline Miss Ratio**:
  $$\text{MR}_{\text{HI}} = \frac{\sum_{\tau_i \in \text{HI}} \text{MissedJobs}(\tau_i)}{\sum_{\tau_i \in \text{HI}} \text{TotalReleasedJobs}(\tau_i)}$$
* **LO Utility Preservation Ratio**:
  $$\text{UPR}_{\text{LO}} = \frac{\sum_{\tau_i \in \text{LO}} \sum_{J_{i,k} \in \text{Completed}} \theta_{i,k} \cdot U_i}{\sum_{\tau_i \in \text{LO}} \sum_{J_{i,k} \in \text{Released}} U_i}$$
* **Computational Overhead Percentage**:
  $$\text{OH}_{\%} = \frac{T_{\text{scheduler}} + T_{\text{risk}} + T_{\text{mode}}}{T_{\text{simulation}}} \times 100\%$$

---

## 6. Experimental Setup

The framework was evaluated using a high-precision, discrete-event simulation engine adhering to strict real-time execution semantics:

* **Simulation Engine**: Custom discrete-event simulator implemented in Python 3.14 with an event priority queue ($O(\log N)$) tracking job releases, execution completions, preemptions, and monitoring checkpoints.
* **Workload Generator**: UUniFast algorithm producing unbiased utilization distributions across tasks. Periods selected log-uniformly in $[20.0, 200.0]$ ms. Deadlines equal periods ($D_i = T_i$).
* **Overrun Multiplier**: HI task execution scaling factor $C(\text{HI}) / C(\text{LO}) = 2.50$.
* **Scenario Profile**: `BOTH_OVERRUN` (HI jobs execute up to $C(\text{HI})$, and LO jobs exhibit nominal load).
* **Workload Configurations**:
  * **Task Set Sizes**: 5, 10, 20, 30, 50 tasks.
  * **Target Nominal Utilizations**: $U \in [0.40, 0.60, 0.80, 1.00, 1.20, 1.40]$.
  * **Criticality Splits ($\text{HI} / \text{LO}$)**: $20/80$, $40/60$, $60/40$.
  * **Task Sets per Configuration**: 5 to 15 independent task sets.
* **Simulation Duration**: $2,000.0$ ms per run (sensitivity and long-run benchmarks up to $5,000.0$ ms).
* **Warm-up Interval**: $200.0$ ms (events prior to warm-up excluded from response time and deadline statistics).
* **Reproducibility**: Deterministic seed generation based on task count, utilization, and index ($800000 \times \text{idx} + U \times 1000 + 42$).
* **Explicit Computational Overhead Model**:
  * $t_{\text{sched}} = 0.010$ ms per scheduling invocation.
  * $t_{\text{risk}} = 0.005$ ms per risk estimation calculation.
  * $t_{\text{mode}} = 0.010$ ms per mode transition.
  * Overhead time is advanced explicitly on the simulated clock without altering task WCETs.

---

## 7. Baseline Comparison

The comprehensive empirical evaluation compares all six target schedulers across 180 multi-run simulations covering utilizations from $0.40$ to $1.40$. The results are summarized in the table below (extracted directly from [results/final_results.csv](file:///home/proster/VS%20Code/AdaptiveGuard/AdaptiveGuard-Scheduler/results/final_results.csv)):

| Scheduler | HI Miss Ratio (mean ± std) | LO Utility Ratio (mean ± std) | LO Completion Ratio (mean ± std) | CPU Utilization (mean ± std) | Avg Response Time (ms) | Worst Response Time (ms) | Mode Switches (mean ± std) | Overhead % (mean ± std) |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| **AdaptiveGuard** | $0.3831 \pm 0.4059$ | **$0.6272 \pm 0.4056$** | **$0.6994 \pm 0.4109$** | $0.9994 \pm 0.1494$ | $108.63 \pm 191.71$ | $239.51 \pm 327.04$ | $33.27 \pm 55.98$ | $7.48\% \pm 1.12\%$ |
| **Flexible MC** | $0.7000 \pm 0.4661$ | $0.7181 \pm 0.2458$ | $0.7218 \pm 0.2439$ | $0.9503 \pm 0.1473$ | $296.54 \pm 263.99$ | $557.77 \pm 436.32$ | $4.00 \pm 0.00$ | $2.33\% \pm 0.70\%$ |
| **EDF-VD + Degraded LO** | $0.2333 \pm 0.4302$ | $0.3331 \pm 0.2074$ | $0.6982 \pm 0.4104$ | $0.8468 \pm 0.1831$ | $104.74 \pm 193.49$ | $221.57 \pm 339.19$ | $1.00 \pm 0.00$ | $2.39\% \pm 0.72\%$ |
| **Classical Reactive MC** | **$0.2333 \pm 0.4302$** | $0.0000 \pm 0.0000$ | $0.0000 \pm 0.0000$ | $0.7066 \pm 0.2365$ | $104.87 \pm 193.44$ | $205.02 \pm 347.54$ | $1.00 \pm 0.00$ | $2.08\% \pm 0.62\%$ |
| **EDF-VD** | **$0.2333 \pm 0.4302$** | $0.0000 \pm 0.0000$ | $0.0000 \pm 0.0000$ | $0.7066 \pm 0.2365$ | $104.87 \pm 193.44$ | $205.02 \pm 347.54$ | $1.00 \pm 0.00$ | **$2.08\% \pm 0.62\%$** |
| **EDF** | $0.7000 \pm 0.4661$ | $0.7181 \pm 0.2458$ | $0.7218 \pm 0.2439$ | $0.9503 \pm 0.1473$ | $296.54 \pm 263.99$ | $557.77 \pm 436.32$ | $0.00 \pm 0.00$ | $2.32\% \pm 0.70\%$ |

### Breakdown by Utilization Range

The interaction between system load and scheduler response highlights critical trade-offs:

1. **Low Load ($U = 0.40$)**:
   * All schedulers achieve **$0.0\%$ HI deadline misses**.
   * AdaptiveGuard, EDF, EDF-VD + Degraded LO, and Flexible MC all achieve **$100.0\%$ LO completion**.
   * Classical MC and EDF-VD prematurely drop LO tasks upon the first overrun event, forfeiting all utility.
2. **Moderate Overload ($U = 0.60 - 0.80$)**:
   * Classical MC and EDF-VD maintain **$0.0\%$ HI deadline misses**, but deliver **$0.0\%$ LO utility**.
   * EDF-VD + Degraded LO maintains **$0.0\%$ HI misses** with $33.31\%$ utility.
   * AdaptiveGuard achieves **$1.1\%$ miss ratio at $U=0.60$** and **$17.9\%$ miss ratio at $U=0.80$**, while preserving **$91.1\%$ to $98.0\%$ LO completion**.
   * EDF and Flexible MC experience complete collapse for HI tasks (**$20.0\%$ to $100.0\%$ miss ratios**).
3. **Severe Overload ($U \ge 1.00$)**:
   * At $U=1.00$, EDF-VD and Classical MC hold HI misses at **$0.0\%$** by eliminating all LO execution.
   * AdaptiveGuard incurs **$46.95\%$ HI misses** at $U=1.00$ and **$89.04\%$ at $U=1.40$** because its active LO jobs and continuous monitoring overhead contend for CPU cycles.

---

## 8. Ablation Study

To evaluate the authentic contribution of each architectural feature, six distinct configurations were evaluated under an identical synthetic overload workload ($T_{\text{sim}} = 200.0$ ms, overload for first 3 jobs). Results from [results/data/ablation_results.csv](file:///home/proster/VS%20Code/AdaptiveGuard/AdaptiveGuard-Scheduler/results/data/ablation_results.csv):

| Config | Architecture Definition | HI Miss % | LO Utility % | LO Completion % | CPU Util % | Mode Switches | Overhead % |
|:---:|---|:---:|:---:|:---:|:---:|:---:|:---:|
| **A** | **EDF-VD** (No proactive risk, no degradation) | **0.0%** | 0.0% | 10.0% | 65.81% | 0 | **0.80%** |
| **B** | **EDF-VD + Generic Degradation** (Uniform $\theta=0.50$, no risk) | **0.0%** | 50.0% | **100.0%** | 88.50% | 0 | 1.01% |
| **C** | **EDF-VD + Proactive Risk** (Risk-based switching, all LO dropped in HI) | **0.0%** | 68.46% | 95.0% | 100.42% | 6 | 4.93% |
| **D** | **EDF-VD + Utility Degradation** (Knapsack degradation, no proactive risk) | **0.0%** | **84.62%** | 55.0% | 100.86% | 0 | 0.86% |
| **E** | **EDF-VD + Risk + Degradation** (No hysteresis, no gradual recovery) | **0.0%** | 80.77% | 95.0% | 105.14% | **39** | 5.14% |
| **F** | **Full AdaptiveGuard** (Risk + Knapsack + Hysteresis + Gradual Recovery) | **0.0%** | 78.97% | 75.0% | 105.05% | **22** | 5.05% |

### Key Findings from Ablation:
1. **Utility-Aware vs Generic Degradation (D vs B)**: Utility-aware knapsack degradation improves LO utility from **$50.0\%$ to $84.62\%$** (+34.62% absolute gain) by selectively allocating capacity to high-density tasks.
2. **Proactive Risk Triggering (C vs A)**: Adding proactive risk monitoring increases utility from **$0.0\%$ to $68.46\%$**, allowing the system to operate safely in `WARNING` mode without dropping tasks.
3. **The Role of Hysteresis (F vs E)**: In Configuration E (without hysteresis), high-frequency risk fluctuations cause **39 mode switches** (chattering). Adding dual-threshold hysteresis in Configuration F reduces mode switches to **22 (a 43.6% reduction in chattering)**, stabilizing execution and lowering overhead.

---

## 9. Sensitivity Analysis

### 9.1 Risk Weight Sensitivity
Evaluating the relative importance of composite risk components ($w_{\text{util}}, w_{\text{laxity}}, w_{\text{overrun}}, w_{\text{deadline}}$) across identical task sets ($U = 1.00$, duration $5000$ ms):

| Weight Configuration | Weights ($w_u / w_l / w_o / w_d$) | HI Miss Ratio | LO Utility Ratio | Mode Switches | Overhead % |
|---|:---:|:---:|:---:|:---:|:---:|
| **Default** | $0.30 / 0.30 / 0.25 / 0.15$ | 0.3950 | 0.6231 | 18.4 | 6.23% |
| **Util-Heavy** | $0.50 / 0.20 / 0.15 / 0.15$ | 0.3950 | 0.6225 | 18.2 | 6.23% |
| **Laxity-Heavy** | $0.20 / 0.50 / 0.15 / 0.15$ | 0.3950 | 0.6232 | 18.5 | 6.23% |
| **Overrun-Heavy** | $0.20 / 0.20 / 0.45 / 0.15$ | 0.3950 | 0.6231 | 18.4 | 6.23% |
| **Deadline-Heavy** | $0.20 / 0.20 / 0.15 / 0.45$ | 0.3950 | 0.6233 | 18.6 | 6.23% |
| **Equal Weights** | $0.25 / 0.25 / 0.25 / 0.25$ | 0.3950 | 0.6231 | 18.4 | 6.23% |

**Observation**: Risk weights show high robustness; minor shifts in weight vectors do not destabilize the system, as utilization and laxity correlate strongly during acute overload.

### 9.2 Threshold Sensitivity
Varying Warning ($W$), HI ($H$), and Recovery ($R$) thresholds:

| Threshold Configuration | HI Miss Ratio | LO Utility Ratio | Mode Switches | Overhead % |
|---|:---:|:---:|:---:|:---:|
| $W=0.50, H=0.75, R=0.30$ | 0.3929 | 0.6241 | 16.2 | 5.99% |
| $W=0.50, H=0.80, R=0.40$ | 0.3929 | 0.6242 | 16.8 | 6.00% |
| $W=0.50, H=0.85, R=0.50$ | 0.3929 | 0.6240 | 17.1 | 6.00% |
| $W=0.60, H=0.75, R=0.30$ | 0.3991 | 0.6185 | 19.4 | 6.14% |
| $W=0.70, H=0.85, R=0.50$ | 0.4082 | 0.6120 | 22.1 | 6.31% |

**Observation**: Setting $W \le 0.50$ provides crucial lead time. Delaying $W$ to $0.70$ compresses the warning window, increasing HI miss ratio by $1.53\%$ and causing more frequent transitions into HI mode.

### 9.3 Monitoring Interval ($\Delta t$) Sensitivity
Varying the periodic monitoring checkpoint spacing across $[0.1, 5.0]$ ms (from [results/data/monitoring_interval_results.csv](file:///home/proster/VS%20Code/AdaptiveGuard/AdaptiveGuard-Scheduler/results/data/monitoring_interval_results.csv)):

| Monitoring Interval $\Delta t$ (ms) | Computational Overhead % | HI Miss Ratio | LO Utility Ratio | Mode Switches |
|:---:|:---:|:---:|:---:|:---:|
| **0.10** | **21.24%** | 0.4215 | 0.5841 | 14.8 |
| **0.25** | 10.19% | 0.3842 | 0.6190 | 27.6 |
| **0.50** (Default) | 7.13% | 0.3831 | 0.6272 | 29.8 |
| **1.00** | 5.81% | 0.3860 | 0.6214 | 30.0 |
| **2.00** | 5.17% | 0.4012 | 0.6085 | 41.0 |
| **5.00** | **5.31%** | **0.4480** | **0.5620** | **74.2** |

**Observation**:
* Very fine checkpoints ($\Delta t = 0.10$ ms) impose unacceptable overhead (**$21.24\%$**), which steals CPU bandwidth and degrades performance.
* Coarse checkpoints ($\Delta t = 5.0$ ms) fail to detect transient spikes in time, increasing HI misses to **$44.80\%$** and mode switches to **$74.2$** due to delayed, jerky control actions.
* The optimal operational balance is achieved between **$\Delta t = 0.50$ ms and $1.00$ ms**, where overhead remains bounded ($5.8\% - 7.1\%$) while maintaining high responsiveness.

---

## 10. Summary of Results

1. **Safety vs Utility Pareto Frontier**:
   * Classical Reactive MC and EDF-VD represent the extreme safety corner: **$23.33\%$ HI misses** (under high overload) but **$0.0\%$ LO utility**.
   * EDF and Flexible MC represent the reckless corner: **$71.81\%$ LO utility** but **$70.00\%$ HI misses**.
   * AdaptiveGuard establishes a superior balanced operating point: **$62.72\%$ LO utility** with a **$38.31\%$ HI miss ratio**.
2. **Computational Overhead Cost**:
   * Continuous risk tracking and knapsack sorting impose an average overhead of **$7.48\%$**, compared to **$2.08\%$** for static baselines.
3. **Chattering Suppression**:
   * The dual-threshold hysteresis mechanism successfully eliminates **$43.6\%$** of mode oscillations under heavy contention.

---

## 11. Limitations and Critical Analysis

To maintain scientific integrity, the following limitations must be stated explicitly:

1. **Higher HI Deadline Misses under Extreme Overload ($U \ge 1.0$)**:
   * AdaptiveGuard **does not outperform EDF-VD or Classical MC in HI deadline miss ratio** when target utilization exceeds $1.0$. At $U=1.20$, AdaptiveGuard exhibits a $74.84\%$ HI miss ratio compared to $60.00\%$ for EDF-VD.
   * **Root Cause**: By design, AdaptiveGuard attempts to keep LO tasks alive at degraded service levels during `WARNING` and `HI` modes. In a saturated system ($U > 1.0$), any processor cycles allocated to LO tasks directly reduce the margin available for overrunning HI tasks. Classical MC guarantees lower HI misses precisely because it ruthlessly executes zero LO instructions after an overrun.
2. **Computational Overhead Burden**:
   * AdaptiveGuard's runtime overhead ($7.48\%$) is more than triple that of static EDF-VD ($2.08\%$). Under high task counts ($N \ge 50$) or aggressive monitoring frequencies ($\Delta t = 0.1$ ms), overhead reaches $21.24\%$, directly worsening deadline misses.
3. **Sensitivity to Tuning**:
   * While risk weights are relatively forgiving, the interaction between warning thresholds ($R_{\text{warn}}$), hysteresis bands, and recovery hold times requires calibration to avoid delayed mode switches.
4. **Knapsack Computational Complexity**:
   * Greedy utility-density sorting runs in $O(N \log N)$. For systems with hundreds of tasks, this re-computation during mode switches would require hardware acceleration or pre-compiled degradation lookup tables.

---

## 12. Conclusion

The empirical findings from this research demonstrate that **AdaptiveGuard successfully solves the all-or-nothing limitation of classical mixed-criticality systems**, achieving:
* **$62.72\%$ average LO utility preservation** (versus $0.0\%$ for EDF-VD and Classical MC).
* **Significant reduction in mode chattering** via hysteresis ($43.6\%$ fewer switches).
* **Smooth, proactive degradation** that avoids immediate task termination during transient surges.

However, the experimental evidence **disproves the hypothesis that AdaptiveGuard is universally superior in every dimension**:
* In safety-critical scenarios where **zero HI deadline misses are mandatory at all costs**, classical reactive abandonment (EDF-VD) remains mathematically and practically superior because it frees 100% of the platform for HI tasks.
* AdaptiveGuard is best suited for **mission-critical cyber-physical systems** (such as autonomous exploration rovers, UAVs, and intelligent robotics) where forfeiting all LO tasks causes mission failure, and where system designers are willing to accept controlled, proactive trade-offs to maximize total delivered operational utility.

---

*Report generated from authentic experimental simulation data recorded in `results/data/` and `results/figures/`.*
