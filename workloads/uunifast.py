"""
UUniFast Algorithm Implementation.

Reference:
Bini, E., & Buttazzo, G. C. (2005). Measuring the performance of schedulability tests.
Real-Time Systems, 30(1-2), 129-154.

Generates controlled, uniformly distributed task utilizations summing exactly to target utilization.
"""

import random
from typing import List, Optional


def uunifast(
    n: int,
    target_utilization: float,
    rng: Optional[random.Random] = None,
) -> List[float]:
    """
    Generate n task utilizations summing to target_utilization using UUniFast algorithm.

    Args:
        n (int): Number of tasks.
        target_utilization (float): Total target utilization sum U.
        rng (random.Random, optional): Random number generator instance.

    Returns:
        List[float]: List of n task utilization values.
    """
    if n <= 0:
        raise ValueError(f"Task count n must be positive, got {n}")
    if target_utilization <= 0.0:
        raise ValueError(f"Target utilization must be positive, got {target_utilization}")

    if rng is None:
        rng = random.Random()

    sum_u = target_utilization
    utilizations: List[float] = []

    for i in range(1, n):
        next_sum_u = sum_u * (rng.random() ** (1.0 / (n - i)))
        utilizations.append(sum_u - next_sum_u)
        sum_u = next_sum_u

    utilizations.append(sum_u)
    return utilizations
