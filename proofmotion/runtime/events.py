"""A run's live event stream.

A pipeline run takes minutes and makes dozens of tool calls. Printing nothing
until it finishes makes it impossible to tell a working run from a stuck one,
or to see *why* the agent chose what it chose. Every stage, tool call, and
artifact is published here as it happens.

Subscribers are optional and the bus is a no-op without them, so instrumenting
the pipeline costs nothing when nobody is watching.
"""

from __future__ import annotations

import queue
import threading
import time
from dataclasses import asdict, dataclass, field
from typing import Any

MAX_HISTORY = 2000


@dataclass
class Event:
    kind: str
    at: float
    data: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventBus:
    """Fan-out of run events, with replay for subscribers that join late."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._subscribers: list[queue.Queue[Event]] = []
        self._history: list[Event] = []
        self._started = time.monotonic()

    def reset(self) -> None:
        with self._lock:
            self._history.clear()
            self._started = time.monotonic()

    def subscribe(self) -> queue.Queue[Event]:
        """Register a listener; it receives the run so far, then live events."""
        listener: queue.Queue[Event] = queue.Queue()
        with self._lock:
            for event in self._history:
                listener.put(event)
            self._subscribers.append(listener)
        return listener

    def unsubscribe(self, listener: queue.Queue[Event]) -> None:
        with self._lock:
            if listener in self._subscribers:
                self._subscribers.remove(listener)

    def emit(self, kind: str, /, **data: Any) -> None:
        """Publish an event.

        `kind` is positional-only so that a payload field may also be called
        "kind" — headlines carry one, and without the `/` every headline raised
        "got multiple values for argument 'kind'".
        """
        event = Event(kind=kind, at=round(time.monotonic() - self._started, 2), data=data)
        with self._lock:
            self._history.append(event)
            if len(self._history) > MAX_HISTORY:
                del self._history[: len(self._history) - MAX_HISTORY]
            listeners = list(self._subscribers)
        for listener in listeners:
            listener.put(event)

    @property
    def history(self) -> list[Event]:
        with self._lock:
            return list(self._history)

    @property
    def watching(self) -> bool:
        with self._lock:
            return bool(self._subscribers)


#: The process-wide bus. The pipeline emits here; the live server listens.
BUS = EventBus()


def stage(name: str, status: str = "start", **detail: Any) -> None:
    """Mark a pipeline stage boundary."""
    BUS.emit("stage", name=name, status=status, **detail)


def headline(text: str, kind: str = "info") -> None:
    """Publish a plain-language note about what just changed or improved.

    kind is one of: info, improved, fixed, warned.
    """
    BUS.emit("headline", text=text, kind=kind)


def artifact(name: str, value: Any) -> None:
    """Publish a structured result: the intent, the plan, the storyboard, the code."""
    BUS.emit("artifact", name=name, value=value)
