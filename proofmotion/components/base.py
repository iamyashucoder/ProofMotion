"""The component registry.

A component is a parameterised, tested builder for a whole visual idea — a
function graph, a Riemann sum, an iteration trace. The model chooses which one
and supplies parameters; the component owns axis ranges, label placement, text
fitting, and fitting to a region.

This is the inversion the quality problem needs. When the model writes layout
code it re-derives every decision from scratch and gets them wrong in a new way
each time. A component gets them right once, is tested at its parameter extremes,
and is versioned so improving it cannot silently change an old project.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel

from proofmotion.runtime.registry import ToolError


@dataclass
class Built:
    """What a component produces."""

    group: Any
    parts: dict[str, Any] = field(default_factory=dict)
    #: Reveal order, as part names. The scene animates these in sequence.
    beats: list[list[str]] = field(default_factory=list)
    notes: str = ""


@dataclass
class Component:
    name: str
    version: int
    domain: str
    summary: str
    params: type[BaseModel]
    build: Callable[..., Built]
    #: Whether this draws a picture, as opposed to setting mathematics.
    #: A question asking for diagrams was answered with equation_chain in every
    #: scene — technically composed, and still four screens of algebra. What
    #: makes a visual explanation visual is not "used a component".
    pictorial: bool = True

    def describe(self) -> dict[str, Any]:
        schema = self.params.model_json_schema()
        return {
            "name": self.name,
            "version": self.version,
            "domain": self.domain,
            "summary": self.summary,
            "parameters": schema.get("properties", {}),
            "required": schema.get("required", []),
        }


COMPONENTS: dict[str, Component] = {}


def component(
    *, version: int, domain: str, params: type[BaseModel], pictorial: bool = True
) -> Callable[[Callable[..., Built]], Callable[..., Built]]:
    """Register a builder. The summary comes from the docstring's first line.

    Pass pictorial=False for a component that sets mathematics rather than
    drawing something, so a run can tell whether it actually produced pictures.
    """

    def register(fn: Callable[..., Built]) -> Callable[..., Built]:
        summary = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else fn.__name__
        COMPONENTS[fn.__name__] = Component(
            name=fn.__name__, version=version, domain=domain, summary=summary,
            params=params, build=fn, pictorial=pictorial,
        )
        return fn

    return register


_LEARNED_LOADED = False


def _load_learned_once() -> bool:
    """Register learned components on first miss. Returns whether anything loaded.

    A rendered scene runs in its own manim process, which imports this module
    but never ran the pipeline — so a scene built from a learned component
    failed with "unknown component" at render time while the same name resolved
    fine everywhere else. Resolving lazily means a scene is self-contained
    whoever wrote it, and costs nothing until a name is actually missing.
    """
    global _LEARNED_LOADED
    if _LEARNED_LOADED:
        return False
    _LEARNED_LOADED = True
    try:
        from proofmotion.learned.store import load_all
    except ImportError:  # pragma: no cover - the package is always present
        return False
    return bool(load_all())


def build(name: str, parameters: dict[str, Any]) -> Built:
    """Validate parameters and build. Invalid parameters raise, never default."""
    if name not in COMPONENTS:
        _load_learned_once()
    if name not in COMPONENTS:
        raise ToolError(f"unknown component {name!r}; available: {sorted(COMPONENTS)}")
    spec = COMPONENTS[name]
    try:
        validated = spec.params.model_validate(parameters)
    except Exception as error:
        raise ToolError(f"{name}: invalid parameters: {error}") from error
    return spec.build(validated)
