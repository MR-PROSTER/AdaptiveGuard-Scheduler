from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from simulator.job import Job
    from simulator.task import Task


class EventType(Enum):
    """Supported simulation event types."""
    JOB_RELEASE = auto()
    JOB_COMPLETION = auto()
    PREEMPTION = auto()
    MONITOR = auto()
    MODE_CHANGE = auto()
    DEADLINE = auto()
    SIMULATION_END = auto()


@dataclass
class Event:
    """
    Simulation Event model.

    Attributes:
        time (float): Event timestamp (ms).
        event_type (EventType): Type of discrete event.
        job (Optional[Job]): Reference to associated Job object, if applicable.
        task (Optional[Task]): Reference to associated Task object, if applicable.
        priority (int): Internal event priority for tie-breaking at same timestamp.
        seq (int): Sequence counter for strict insertion ordering in min-heap.
        payload (Optional[Dict[str, Any]]): Additional metadata payload.
    """

    time: float
    event_type: EventType
    job: Optional["Job"] = None
    task: Optional["Task"] = None
    priority: int = 0
    seq: int = field(default=0, repr=False)
    payload: Optional[Dict[str, Any]] = None

    def __lt__(self, other: "Event") -> bool:
        """Min-heap comparison based on timestamp, priority, and insertion sequence."""
        if abs(self.time - other.time) > 1e-9:
            return self.time < other.time
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.seq < other.seq
