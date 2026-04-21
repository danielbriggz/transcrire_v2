from collections import defaultdict
from typing import Callable


class EventEmitter:
    """
    Lightweight synchronous event emitter.

    Intended events (not exhaustive):
        stage_started    → {"job_id": ..., "stage": ...}
        stage_completed  → {"job_id": ..., "stage": ..., "duration_ms": ...}
        stage_failed     → {"job_id": ..., "stage": ..., "error": ...}
        progress_update  → {"job_id": ..., "percent": ...}
    """

    def __init__(self):
        self._listeners: dict[str, list[Callable]] = defaultdict(list) # pyright: ignore[reportMissingTypeArgument]

    def on(self, event: str, callback: Callable) -> None: # type: ignore
        """Register a listener for an event type."""
        self._listeners[event].append(callback) # type: ignore

    def off(self, event: str, callback: Callable) -> None: # type: ignore
        """Remove a specific listener."""
        self._listeners[event] = [ # type: ignore
            cb for cb in self._listeners[event] if cb != callback # type: ignore
        ]

    def emit(self, event: str, payload: dict = None) -> None: # type: ignore
        """Fire an event to all registered listeners."""
        for callback in self._listeners.get(event, []): # type: ignore
            callback(payload or {})

    def clear(self, event: str = None) -> None: # type: ignore
        """Remove all listeners, or all listeners for a specific event."""
        if event:
            self._listeners[event] = [] # type: ignore
        else:
            self._listeners.clear() # type: ignore


# Single shared instance
emitter = EventEmitter()