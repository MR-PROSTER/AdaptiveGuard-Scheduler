import heapq
from typing import List, Optional
from simulator.event import Event


class EventQueue:
    """
    Priority Queue for simulation events using Python's `heapq` module.
    Ensures events are processed in chronological order.
    """

    def __init__(self) -> None:
        self._heap: List[Event] = []
        self._counter: int = 0

    def push(self, event: Event) -> None:
        """Push an event into the priority queue."""
        self._counter += 1
        event.seq = self._counter
        heapq.heappush(self._heap, event)

    def pop(self) -> Event:
        """Pop the earliest event from the priority queue."""
        if not self._heap:
            raise IndexError("pop from an empty EventQueue")
        return heapq.heappop(self._heap)

    def peek(self) -> Optional[Event]:
        """View the next scheduled event without removing it."""
        return self._heap[0] if self._heap else None

    def is_empty(self) -> bool:
        """Check if the event queue is empty."""
        return len(self._heap) == 0

    def size(self) -> int:
        """Return total pending events in queue."""
        return len(self._heap)

    def clear(self) -> None:
        """Clear all events from queue."""
        self._heap.clear()
        self._counter = 0
