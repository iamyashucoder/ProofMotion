"""Edits to a project, as operations rather than a regenerated plan.

A follow-up must not restate the whole answer. "Now show what happens as n
grows" is two added slides, and everything already rendered has to survive
untouched — if a turn re-emits the document, every clip's content hash changes
and the whole video re-renders, which is the cost this design exists to avoid.

So a turn produces a diff. That is also what makes multi-turn tractable for the
model: a handful of operations is small structured output, where a whole
storyboard is where a local model ran out of budget mid-JSON.

Everything here is a pure function over the document, testable without a model.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components import COMPONENTS
from proofmotion.runtime.registry import ToolError
from proofmotion.studio.document import Project, Slide


class Operation(BaseModel):
    """One edit. `kind` decides which fields matter."""

    kind: Literal["add", "edit", "set_parameter", "reorder", "delete", "lock"]
    #: The slide acted on. Empty for `add`.
    slide_id: str = ""
    #: For `add`: place after this slide, or at the end when empty.
    after: str = ""
    title: str | None = None
    component: str | None = None
    parameters: dict[str, Any] | None = None
    caption: str | None = None
    seconds: float | None = None
    #: For `set_parameter`.
    name: str = ""
    value: Any = None
    #: For `lock`.
    locked: bool = True
    #: Why, in a few words. Shown to the person in the transcript.
    reason: str = ""


class Edit(BaseModel):
    """What a turn proposes."""

    operations: list[Operation] = Field(default_factory=list, max_length=20)
    reply: str = Field(default="", description="One or two sentences for the person.")
    #: Set when the message asks for something that needs deriving rather than
    #: editing — a new part of the problem, a fresh question. The caller then
    #: runs the full pipeline instead of applying these operations, because a
    #: tweak agent inventing mathematics is how a deck gets confident and wrong.
    needs_full_derivation: bool = Field(
        default=False,
        description="True when the ask needs mathematics worked out, not a slide edited.",
    )


def _check_component(name: str | None, parameters: dict[str, Any]) -> None:
    """Refuse a slide the renderer could not build, before it is stored.

    A bad component reaches the cache as a failing unit and stays there. It is
    cheaper and far clearer to reject it while the operation is still an
    operation.
    """
    if name is None:
        return
    spec = COMPONENTS.get(name)
    if spec is None:
        raise ToolError(f"unknown component {name!r}; available: {sorted(COMPONENTS)}")
    try:
        spec.params.model_validate(parameters)
    except Exception as error:
        raise ToolError(f"{name}: {error}") from error


def apply(project: Project, operation: Operation) -> Project:
    """Apply one operation, returning the same project mutated in place."""
    kind = operation.kind

    if kind == "add":
        parameters = operation.parameters or {}
        _check_component(operation.component, parameters)
        slide = Slide(
            id=project.next_id(),
            title=operation.title or "",
            component=operation.component,
            parameters=parameters,
            caption=operation.caption or "",
            seconds=operation.seconds or 6.0,
        )
        if not slide.component and not slide.caption and not slide.title:
            raise ToolError("a slide needs a component, a caption, or a title")
        position = project.index_of(operation.after) + 1 if operation.after else len(project.slides)
        project.slides.insert(position, slide)
        return project

    slide = project.slide(operation.slide_id)

    if kind == "lock":
        slide.locked = operation.locked
        return project

    if slide.locked:
        # The promise that makes a studio usable. An agent may propose changes
        # to a slide the person has settled; it may not make them.
        raise ToolError(f"slide {slide.id} is locked; unlock it before editing")

    if kind == "delete":
        project.slides.remove(slide)
        return project

    if kind == "reorder":
        project.slides.remove(slide)
        position = project.index_of(operation.after) + 1 if operation.after else len(project.slides)
        project.slides.insert(position, slide)
        return project

    if kind == "set_parameter":
        if not operation.name:
            raise ToolError("set_parameter needs a parameter name")
        merged = {**slide.parameters, operation.name: operation.value}
        _check_component(slide.component, merged)
        slide.parameters = merged
        return project

    if kind == "edit":
        component = slide.component if operation.component is None else operation.component
        parameters = slide.parameters if operation.parameters is None else operation.parameters
        _check_component(component, parameters)
        slide.component, slide.parameters = component, parameters
        if operation.title is not None:
            slide.title = operation.title
        if operation.caption is not None:
            slide.caption = operation.caption
        if operation.seconds is not None:
            slide.seconds = operation.seconds
        return project

    raise ToolError(f"unknown operation {kind!r}")


def apply_all(project: Project, operations: list[Operation]) -> dict[str, Any]:
    """Apply operations in order, reporting each outcome.

    One bad operation does not discard the rest. A turn that adds three slides
    and mistypes a parameter on the second should still deliver the other two,
    with the failure reported rather than swallowed.
    """
    applied, refused = [], []
    before = {s.id for s in project.slides}
    for operation in operations:
        try:
            apply(project, operation)
            applied.append(operation)
        except ToolError as error:
            refused.append({"operation": operation.kind, "slide": operation.slide_id, "problem": str(error)})
    if applied:
        project.revision += 1
    after = {s.id for s in project.slides}
    return {
        "applied": len(applied),
        "refused": refused,
        "added": sorted(after - before),
        "removed": sorted(before - after),
    }


def touched(operations: list[Operation]) -> list[str]:
    """Slide ids an edit changed, for forcing a re-render of just those."""
    return sorted({o.slide_id for o in operations if o.slide_id and o.kind != "lock"})
