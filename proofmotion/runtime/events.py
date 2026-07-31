"""A run's live event stream.

A pipeline run takes minutes and makes dozens of tool calls. Printing nothing
until it finishes makes it impossible to tell a working run from a stuck one,
or to see *why* the agent chose what it chose. Every stage, tool call, and
artifact is published here as it happens.

Subscribers are optional and the bus is a no-op without them, so instrumenting
the pipeline costs nothing when nobody is watching.
"""

from __future__ import annotations

import contextvars
import queue
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any, Iterator

MAX_HISTORY = 2000

#: Which project the current thread of work belongs to. The bus is process-wide
#: and the studio serves many projects at once, so every event carries this —
#: otherwise one project's render progress lands in another project's stream.
_PROJECT: contextvars.ContextVar[str] = contextvars.ContextVar("project", default="")


@contextmanager
def scoped(project_id: str) -> Iterator[None]:
    """Stamp every event emitted inside with the project it belongs to.

    A context variable rather than an argument, because the emitters are deep
    inside the pipeline and the render loop — none of which should know that
    projects exist.
    """
    token = _PROJECT.set(project_id)
    try:
        yield
    finally:
        _PROJECT.reset(token)


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

    def subscribe(self, replay: int | None = None) -> queue.Queue[Event]:
        """Register a listener; it receives the run so far, then live events.

        `replay` bounds how much of the past a late subscriber is handed:
        None means everything (the live pipeline view wants the whole run),
        0 means only what happens next. A page refresh mid-session used to be
        handed the entire history and finish on a status line from an hour ago.
        """
        listener: queue.Queue[Event] = queue.Queue()
        with self._lock:
            past = self._history if replay is None else (self._history[-replay:] if replay else [])
            for event in past:
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
        data.setdefault("project", _PROJECT.get())
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
