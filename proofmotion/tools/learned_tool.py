"""Reading a component, and writing a better one.

Two tools close the loop the library could not close on its own. `component_source`
lets a model read what a component actually does, so a rewrite starts from
working code rather than from the summary line. `component_learn` admits the
rewrite and keeps it, so the next question that needs it finds it already there.
"""

from __future__ import annotations

import inspect
from typing import Any

from proofmotion.components import COMPONENTS
from proofmotion.learned import admit, store
from proofmotion.runtime.registry import ToolError, tool

TEMPLATE = '''from manim import *
from pydantic import BaseModel, Field

from proofmotion.components.base import Built
from proofmotion.layout.regions import layout, place


class Params(BaseModel):
    """Every parameter the component takes, with types and defaults."""


def build(p: Params) -> Built:
    parts = {}
    # ... construct mobjects, put each named piece in `parts` ...
    group = VGroup(*parts.values())
    return Built(group=group, parts=parts, beats=[[name] for name in parts], notes="")
'''


@tool
def component_source(name: str) -> dict[str, Any]:
    """Read a component's implementation, to understand or rewrite it.

    Returns the parameter model and the builder as source. Use this when a
    component is close to what a scene needs but not right — reading how it
    derives its ranges and places its labels is what makes a rewrite better
    than starting over.

    Args:
        name: Component name from component_search.
    """
    spec = COMPONENTS.get(name)
    if spec is None:
        raise ToolError(f"unknown component {name!r}; available: {sorted(COMPONENTS)}")

    try:
        params_source = inspect.getsource(spec.params)
        build_source = inspect.getsource(spec.build)
    except (OSError, TypeError) as error:
        raise ToolError(f"cannot read the source of {name!r}: {error}") from error

    return {
        "name": name,
        "version": spec.version,
        "domain": spec.domain,
        "summary": spec.summary,
        "learned": bool(getattr(spec, "learned", False)),
        "parent": getattr(spec, "parent", None),
        "params_source": params_source,
        "build_source": build_source,
        "note": (
            "To keep a variant, call component_learn with a complete module: a Params "
            "class and a build(p) function returning Built. Give it a new name."
        ),
    }


@tool
def component_learn(
    name: str,
    source: str,
    example_parameters: dict,
    summary: str,
    domain: str = "learned",
    parent: str = "",
) -> dict[str, Any]:
    """Keep a component you have written, so future questions can use it.

    The source must be a complete module defining a `Params` model and a
    `build(p)` function returning Built. It is admitted before it is kept: it
    must load, validate its own example parameters, build real geometry twice
    with identical results, keep that geometry inside the frame, and not place
    text over its own ink. If any of that fails you get the reason back and
    nothing is saved.

    Write a variant when a component is nearly right but not right — a different
    reveal order, an extra annotation, a range derived differently. Give it its
    own name and say in the summary what it does that the parent does not.

    Args:
        name: New lowercase identifier, e.g. "tangent_secant_with_normal".
        source: The complete module source.
        example_parameters: Parameters the component is built with to check it.
        summary: One line: what it draws, and how it differs from its parent.
        domain: Subject area, e.g. "calculus", "mechanics".
        parent: The component this was rewritten from, if any.
    """
    store.check_name(name)
    if parent and parent not in COMPONENTS:
        raise ToolError(f"unknown parent {parent!r}; available: {sorted(COMPONENTS)}")
    if not summary.strip():
        raise ToolError("summary is required: a component nobody can identify will not be found again")

    verdict = admit(source, name, example_parameters)
    if not verdict.ok:
        return {
            "kept": False,
            "name": name,
            "problems": verdict.problems,
            "advice": "Fix these and call component_learn again. Nothing was saved.",
            "template": TEMPLATE,
        }

    record = store.save(
        name=name,
        source=source,
        domain=domain,
        summary=summary.strip(),
        example_parameters=example_parameters,
        parts=verdict.parts,
        beats=verdict.beats,
        parent=parent or None,
        prompt=_current_prompt(),
        project_id=_current_project(),
    )
    return {
        "kept": True,
        "name": name,
        "version": record.version,
        "parts": verdict.parts,
        "beats": verdict.beats,
        "usage": (
            f"from proofmotion.components import build\n"
            f'built = build("{name}", {example_parameters!r})'
        ),
        "note": "Registered now — usable in this run and found by component_search in future runs.",
    }


def _current_prompt() -> str:
    """The question that prompted this component, from the run's own events."""
    from proofmotion.runtime.events import BUS

    for event in BUS.history:
        if event.kind == "run":
            return str(event.data.get("prompt", ""))
    return ""


def _current_project() -> str:
    from proofmotion.runtime.events import BUS

    for event in BUS.history:
        if event.kind == "run":
            return str(event.data.get("project", ""))
    return ""
