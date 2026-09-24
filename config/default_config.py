from dataclasses import dataclass

@dataclass
class SimulationConfig:
    """
    Default configuration parameters for the AdaptiveGuard discrete-event simulator.
    """
    duration: float = 100.0       # Total simulation duration in milliseconds
    cpu_speed: float = 1.0        # Default CPU speed factor
    time_unit: str = "ms"         # Unit of time
    verbose: bool = True          # Enable event logging output
