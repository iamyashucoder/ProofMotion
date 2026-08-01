"""Read a scene plan straight out of the storyboard.

The director already names components and their parameters — it searches for
them and builds them to check the geometry, twenty-odd tool calls of work. Then
the selector was asking a second model to decide the same thing again.

So try the storyboard first. When its visual objects name real components with
parameters that validate, the plan is already written and assembly costs nothing
at all: no round trip, no tokens, no waiting. The selector stays for the case
this cannot cover, which is a storyboard describing shapes rather than
components.

Nothing here guesses. A visual object that is not a registered component, or
whose parameters do not validate, is passed over rather than coerced.
"""

from __future__ import annotations

from typing import Any

from proofmotion.components import COMPONENTS
from proofmotion.compose.assembler import SceneAssignment, ScenePlan, check
from schemas.storyboard import MAX_SCENES


def _component_from(objects: list[Any]) -> tuple[str | None, dict[str, Any]] | None:
    """The scene's component, or None when the storyboard describes more than one.

    Taking the first match is wrong, and quietly so. A director describing a
    tangent scene writes function_plot first and then the tangent line as a
    loose shape, so the first match renders the plot alone — four identical
    parabolas for four different scenes, each of them individually valid.

    So a component is only read off a scene when it accounts for everything in
    it. Anything left over means the storyboard is saying something the
    component does not, and that scene belongs to the selector.
    """
    matched: tuple[str, dict[str, Any]] | None = None
    for entry in objects:
        if not isinstance(entry, dict):
            return None
        name = entry.get("name")
        spec = COMPONENTS.get(name) if isinstance(name, str) else None
        parameters = entry.get("parameters")
        if spec is None or not isinstance(parameters, dict):
            return None
        try:
            spec.params.model_validate(parameters)
        except Exception:  # noqa: BLE001 - an invalid object is not a match
            return None
        # Pydantic ignores keys it does not know, and the director invents
        # them: "angle" for angle_deg, "show_sine" for show_sin. Extras
        # slipping through here validated a guessed schema as if it were
        # real, and twelve slides later every operation was refused at the
        # gate that does check. A scene with invented parameters belongs to
        # the selector, which reads the real schema before answering.
        if set(parameters) - set(spec.params.model_fields):
            return None
        if matched is not None:
            # Two components in one scene is a composition question — which
            # sits where — and this cannot answer it.
            return None
        matched = (name, parameters)
    return matched if matched else (None, {})


def plan_from_storyboard(storyboard: dict[str, Any]) -> ScenePlan | None:
    """Build a scene plan from the director's own choices, or None.

    Returns None rather than a partial plan: a storyboard the assembler cannot
    read is the selector's job, and a half-derived plan would quietly drop
    whatever the director had asked for.
    """
    scenes = storyboard.get("scenes") or []
    if not scenes:
        return None

    assignments: list[SceneAssignment] = []
    for scene in scenes[:MAX_SCENES]:  # the plan's own limit
        if not isinstance(scene, dict):
            return None
        match = _component_from(scene.get("visual_objects") or [])
        if match is None:
            return None
        component, parameters = match
        equations = [e for e in (scene.get("equations") or []) if isinstance(e, str) and e.strip()]
        if component is None and not equations:
            # Nothing to draw and nothing to show. The selector may still find a
            # component from the scene's purpose, so hand the whole thing over.
            return None
        assignments.append(
            SceneAssignment(
                # The director's own heading. Never `purpose`, which is a
                # sentence written for the pipeline: rendered as a title it
                # gets shrunk to fit and reads as a caption in the wrong place.
                title=str(scene.get("title") or "").strip()[:60],
                component=component,
                parameters=parameters,
                caption=equations[0] if equations else "",
                read_from_previous=[item for item in (scene.get("read_from_previous") or []) if item in {"diagram", "equation"}],
                bridge_text=str(scene.get("bridge_text") or "")[:120],
                forget_after=[item for item in (scene.get("forget_after") or []) if item in {"diagram", "equation"}],
                seconds=min(40.0, max(1.0, float(scene.get("duration_seconds") or 6.0))),
                # The director writes narration for every scene; dropping it
                # here is why it was generated on every run and reached nothing.
                narration=str(scene.get("narration") or "").strip(),
            )
        )

    plan = ScenePlan(assignments=assignments)
    if check(plan):
        return None
    if not any(a.component for a in plan.assignments):
        # Every scene came out as an equation slide. That is a storyboard the
        # director never grounded in components, and the selector should look
        # at it properly rather than this producing a wall of text.
        return None
    return plan
