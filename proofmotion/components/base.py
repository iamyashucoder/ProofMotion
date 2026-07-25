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


def component(*, version: int, domain: str, params: type[BaseModel]) -> Callable[[Callable[..., Built]], Callable[..., Built]]:
    """Register a builder. The summary comes from the docstring's first line."""

    def register(fn: Callable[..., Built]) -> Callable[..., Built]:
        summary = (fn.__doc__ or "").strip().splitlines()[0] if fn.__doc__ else fn.__name__
        COMPONENTS[fn.__name__] = Component(
            name=fn.__name__, version=version, domain=domain, summary=summary, params=params, build=fn
        )
        return fn

    return register


def build(name: str, parameters: dict[str, Any]) -> Built:
    """Validate parameters and build. Invalid parameters raise, never default."""
    if name not in COMPONENTS:
        raise ToolError(f"unknown component {name!r}; available: {sorted(COMPONENTS)}")
    spec = COMPONENTS[name]
    try:
        validated = spec.params.model_validate(parameters)
    except Exception as error:
        raise ToolError(f"{name}: invalid parameters: {error}") from error
    return spec.build(validated)
