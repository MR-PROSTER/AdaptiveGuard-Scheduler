# AdaptiveGuard: Proactive and Graceful Mixed-Criticality Scheduling

AdaptiveGuard is a research-grade Python discrete-event simulator for Mixed-Criticality (MC) Real-Time Systems. This initial phase establishes the simulator foundation, data models, event-driven engine, single-CPU execution model, and discrete-event simulation pipeline.

## Project Architecture

```
AdaptiveGuard-Scheduler/
├── README.md
├── config/
│   ├── __init__.py
│   └── default_config.py
├── simulator/
│   ├── __init__.py
│   ├── task.py
│   ├── job.py
│   ├── event.py
│   ├── cpu.py
│   ├── clock.py
│   ├── event_queue.py
│   └── simulation.py
├── workloads/
│   ├── __init__.py
│   └── fixed_workload.py
├── tests/
│   ├── __init__.py
│   ├── test_task.py
│   └── test_job.py
└── main.py
```

## Data Models & Specifications

- **Task Model (`task.py`)**:
  - `task_id`, `name`, `criticality` (`HI` or `LO`), `period` ($T_i$), `relative_deadline` ($D_i$), `C_LO`, `C_HI`, `utility`, `minimum_service`, `maximum_service`, `release_offset`.
  - Enforces Mixed-Criticality validation rules:
    - HI tasks: $C_{LO} < C_{HI}$
    - LO tasks: $C_{LO} == C_{HI}$
    - Primary experiments: $D_i = T_i$

- **Job Model (`job.py`)**:
  - `job_id`, `task`, `release_time`, `absolute_deadline`, `required_execution`, `remaining_execution`, `executed_time`, `completion_time`, `completed`, `missed_deadline`.
  - Job release time: $r_{i,k} = \text{offset}_i + k \cdot T_i$
  - Job absolute deadline: $d_{i,k} = r_{i,k} + D_i$

- **Event Engine (`event.py`, `event_queue.py`, `clock.py`)**:
  - Event types: `JOB_RELEASE`, `JOB_COMPLETION`, `PREEMPTION`, `MONITOR`, `MODE_CHANGE`, `DEADLINE`, `SIMULATION_END`.
  - Min-heap Priority Queue using Python's `heapq` module.
  - Simulation clock operating in milliseconds (ms).

- **CPU Model (`cpu.py`)**:
  - Single CPU core with `speed = 1.0`.
  - Job execution tracking, preemption support, and idle/busy time tracking.

- **Simulation (`simulation.py`)**:
  - Discrete-event simulation loop managing job releases, ready queue dispatching, CPU execution, deadline checks, and metrics collection.

## Running Tests

To run unit tests with `pytest`:

```bash
python3 -m pytest tests/
```

## Running the Simulator

To run the simulator main script:

```bash
python3 main.py
```
