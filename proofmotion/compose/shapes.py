"""Shape-first selection: the paragraph and the fallback, in one place.

Five shapes cover most of what an explanation ever needs, and the prompt that
says so is shared by the three agents that choose components — selector,
director, and the studio's edit agent — because three hand-kept copies of one
idea is how the idea quietly stops being true in one of them.
"""

from __future__ import annotations

from typing import Any

#: Inserted verbatim into the three selection prompts. The wording matters:
#: the question it plants — "what shape is this idea?" — is the one that finds
#: flow_diagram for a process and comparison for a trade-off, which a search
#: over subject words never surfaces.
SHAPE_FIRST = """Before you search, name the shape of the idea. Most explanations are one of
five shapes, and each has a component that draws it from labels alone:
- a process, a derivation, a pipeline is a sequence — flow_diagram
- this-versus-that, before-and-after, a trade-off is a comparison — comparison
- a taxonomy, a decomposition, what-contains-what is a tree — hierarchy
- an architecture, a protocol stack, levels of abstraction are a stack — layers
- a table, a matrix, a state space is a grid — grid_map
A scene with no subject component still has a shape, and the shape component
is the answer for it. Reach for null, a bare caption, or hand-drawn code only
when the idea genuinely has none of these shapes."""

#: Question words that mark a stack of levels rather than a sequence of steps.
_STACKED = ("stack", "layer", "layers", "architecture", "protocol", "abstraction")


def shape_fallback(state: dict[str, Any]) -> list:
    """The plan's structure as a shape, when the plan drew nothing at all.

    A derivation is a sequence and so is a process; the plan already holds it
    in order. Drawing that costs one slide and gives the deck a shape to hang
    the words on, which is the difference between watching an explanation and
    reading one.

    Only the shapes whose labels the plan actually holds are routed here: the
    concept sequence is genuinely a sequence (or a stack, when the question
    says so). Rows of a comparison and edges of a tree need labels the plan
    does not carry in pairs, and inventing them draws something confidently
    wrong — those shapes are reached through the prompt, where the model
    supplies the labels.
    """
    from proofmotion.studio.operations import Operation

    steps = (state.get("math_plan") or {}).get("concept_sequence") or []
    stages = [str(s.get("concept", "")).strip() for s in steps]
    stages = [s[:26] for s in stages if s]
    if len(stages) < 2:
        return []

    intent = state.get("intent") or {}
    topic = str(intent.get("topic") or "The whole process")
    asked = f"{topic} {intent.get('domain', '')}".lower()

    if any(word in asked.split() for word in _STACKED) and 2 <= len(stages) <= 7:
        return [Operation(
            kind="add", title=topic[:56], component="layers",
            parameters={"layers": stages, "annotations": [], "highlight": []},
            seconds=10.0, reason="the levels of it, before their details",
        )]

    if len(stages) > 8:
        # Sampled evenly across the whole sequence, which keeps both ends. An
        # earlier version appended the last stage and then truncated to eight,
        # so a thirteen-step process lost the step it was working towards.
        last = len(stages) - 1
        chosen = sorted({round(i * last / 7) for i in range(8)})
        stages = [stages[i] for i in chosen]

    return [Operation(
        kind="add", title=topic[:56], component="flow_diagram",
        parameters={"stages": stages, "highlight": [], "feedback": False},
        seconds=10.0, reason="the shape of the argument, before its steps",
    )]
