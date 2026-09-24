"""
Synthetic Taskset Generator for Mixed-Criticality Research Experiments.

Uses UUniFast to generate controlled synthetic tasksets across configured parameters:
- Task counts: 5, 10, 20, 30, 50
- Target utilizations: 0.40, 0.50, 0.60, 0.70, 0.80, 0.90, 1.00, 1.10, 1.20, 1.30, 1.40, 1.50
- HI/LO ratios: 20/80, 40/60, 60/40
- Period options: 5, 10, 20, 50, 100 ms
- C_HI factor: 2.5 (configurable)
"""

from dataclasses import dataclass
import random
from typing import List, Dict, Any, Optional
from simulator.task import Task, Criticality
from workloads.uunifast import uunifast


@dataclass
class TasksetMetrics:
    """
    Summary metrics for a generated mixed-criticality taskset.
    """

    U_LO: float
    U_HI_LO: float
    U_HI_HI: float
    U_total_LO: float
    U_total_HI: float


class TasksetGenerator:
    """
    Generator for synthetic mixed-criticality tasksets.
    """

    DEFAULT_PERIODS = (5.0, 10.0, 20.0, 50.0, 100.0)

    def __init__(
        self,
        c_hi_factor: float = 2.5,
        period_options: Optional[List[float]] = None,
    ) -> None:
        self.c_hi_factor: float = c_hi_factor
        self.period_options: List[float] = period_options or list(self.DEFAULT_PERIODS)

    def generate_taskset(
        self,
        num_tasks: int,
        target_utilization: float,
        hi_ratio: float = 0.40,
        seed: int = 42,
    ) -> List[Task]:
        """
        Generate a single synthetic taskset.

        Args:
            num_tasks (int): Number of tasks.
            target_utilization (float): Target total LO-utilization sum U.
            hi_ratio (float): Fraction of tasks that are HI criticality (e.g. 0.2, 0.4, 0.6).
            seed (int): Random seed for reproducible generation.

        Returns:
            List[Task]: List of generated Task objects.
        """
        rng = random.Random(seed)
        utilizations = uunifast(num_tasks, target_utilization, rng=rng)

        num_hi = int(round(num_tasks * hi_ratio))
        num_hi = max(1, min(num_tasks - 1, num_hi)) if num_tasks > 1 else num_hi

        tasks: List[Task] = []
        for i in range(num_tasks):
            t_id = i + 1
            is_hi = i < num_hi
            crit = Criticality.HI if is_hi else Criticality.LO

            period = rng.choice(self.period_options)
            u_i = utilizations[i]
            c_lo = max(0.1, round(u_i * period, 4))
            c_hi = round(c_lo * self.c_hi_factor, 4) if is_hi else c_lo

            # Application utility: HI tasks = 0, LO tasks = 10 to 100
            utility = 0.0 if is_hi else float(rng.choice([10, 20, 50, 100]))

            task = Task(
                task_id=t_id,
                name=f"{'H' if is_hi else 'L'}{t_id}",
                criticality=crit,
                period=period,
                relative_deadline=period,
                C_LO=c_lo,
                C_HI=c_hi,
                utility=utility,
                minimum_service=1.0 if is_hi else 0.0,
                maximum_service=1.0,
                release_offset=0.0,
            )
            tasks.append(task)

        return tasks

    @staticmethod
    def calculate_taskset_metrics(tasks: List[Task]) -> TasksetMetrics:
        """
        Calculate utilization breakdown metrics for a taskset.

        Formulas:
          U_LO       = sum(C_LO / T) for LO tasks
          U_HI_LO    = sum(C_LO / T) for HI tasks
          U_HI_HI    = sum(C_HI / T) for HI tasks
          U_total_LO = U_LO + U_HI_LO
          U_total_HI = U_LO + U_HI_HI
        """
        u_lo = sum(t.C_LO / t.period for t in tasks if t.criticality == Criticality.LO)
        u_hi_lo = sum(t.C_LO / t.period for t in tasks if t.criticality == Criticality.HI)
        u_hi_hi = sum(t.C_HI / t.period for t in tasks if t.criticality == Criticality.HI)

        return TasksetMetrics(
            U_LO=u_lo,
            U_HI_LO=u_hi_lo,
            U_HI_HI=u_hi_hi,
            U_total_LO=u_lo + u_hi_lo,
            U_total_HI=u_lo + u_hi_hi,
        )
