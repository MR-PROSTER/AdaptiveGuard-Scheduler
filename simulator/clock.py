class SimulationClock:
    """
    Simulation Clock tracking simulation time in milliseconds (ms).
    """

    def __init__(self, initial_time: float = 0.0) -> None:
        self._current_time: float = initial_time

    @property
    def current_time(self) -> float:
        """Get current simulation time (ms)."""
        return self._current_time

    def advance_to(self, new_time: float) -> None:
        """Advance current time to target time."""
        if new_time < self._current_time:
            raise ValueError(
                f"Cannot rewind clock from {self._current_time} to {new_time}"
            )
        self._current_time = new_time

    def step(self, delta: float) -> None:
        """Advance time forward by delta ms."""
        if delta < 0:
            raise ValueError(f"Time step delta cannot be negative: {delta}")
        self._current_time += delta

    def reset(self, initial_time: float = 0.0) -> None:
        """Reset clock to specified initial time."""
        self._current_time = initial_time
