"""Turn verified mathematics into a storyboard, with the frame actually measured.

Replaces a storyboard written by hand for one topic. The director now measures
text before placing it, because guessing is what produced overlapping labels in
every scene tested — including the hand-written one.
"""

from __future__ import annotations

from typing import Any

from proofmotion.runtime.loop import run_structured
from proofmotion.tools import toolset
from schemas.intent import AnimationIntent
from schemas.math_plan import MathematicalPlan
from schemas.storyboard import Storyboard

SYSTEM = """You design how a mathematical explanation should look and unfold.

One idea per scene. Introduce an object before referring to it, and give the
viewer time to read anything you put on screen.

The scene budget you are given is a limit. Scenes that exist only to restate
what was just shown should be cut.

Express each scene as one component. Call component_search to see what exists
and component_build to check the parameters you intend, then put that single
component in visual_objects with the parameters you verified:

    "visual_objects": [{"name": "tangent_secant",
                        "parameters": {"expr": "(x-2)**2+1", "x_min": 0,
                                       "x_max": 5, "at": 3.0}}]

Choose the component that already contains what the scene is about. A scene
showing a tangent is tangent_secant — not function_plot with a tangent line
listed beside it. Loose shapes alongside a component mean the component is the
wrong one, and a scene assembled from it would leave out the very thing the
scene is for.

If no single component expresses a scene, leave visual_objects empty and put the
mathematics in equations. That is a real answer and a much better one than a
component that nearly fits.

Several scenes may name the same component with the same parameters. That is
expected when an explanation stays with one figure and builds on it — the figure
is held on screen and the words change around it, so you do not need to invent
variation to avoid repeating yourself.

Do not plan placement. Where things sit, what order they appear in, and what
leaves the screen between scenes are decided after you, by the assembler and by
the components themselves — a component owns its own axis ranges, label
positions and text fitting. Choosing the right component is how you control the
picture; arranging it is not your decision to make.

Confirm every equation typesets with typeset_check before putting it in a scene.

Ask for everything you need in one turn rather than one call at a time. Four
searches in a single turn cost one round trip; four separate turns cost four,
and round trips are most of the time this stage takes.

Give each scene a purpose, a duration proportional to how much there is to read,
and narration that would make sense read aloud.

Give each scene a title too: the few words that go on screen above it, like
"Slope of the tangent". That is not the purpose restated — the purpose is a
sentence for the pipeline, and a sentence rendered as a heading gets shrunk
until it reads as a caption in the wrong place."""


def direct_storyboard(
    client: Any,
    intent: AnimationIntent,
    plan: MathematicalPlan,
    verification: dict[str, Any],
) -> Storyboard:
    """Compose a storyboard from the verified plan."""
    steps = "\n".join(
        f"  {s.index}. {s.concept}: {s.equation_latex or '(prose)'} — {s.explanation}"
        for s in plan.concept_sequence
    )
    return run_structured(
        client,
        SYSTEM,
        (
            f"Topic: {intent.topic}\n"
            f"Audience: {intent.audience} ({intent.difficulty})\n"
            f"Goal: {intent.educational_goal}\n"
            f"Target length: about {intent.duration_seconds} seconds\n"
            f"Budget: at most {max(3, min(6, round(intent.duration_seconds / 8)))} scenes, "
            f"and the scene durations must total close to {intent.duration_seconds}s\n"
            f"Mathematics verified: {verification['valid']}\n\n"
            f"Verified steps:\n{steps}\n\n"
            "Design the storyboard."
        ),
        # Only what the director still decides. It used to hold the layout
        # tools and spent nine of twenty-two calls measuring hypothetical text
        # boxes — placement it no longer owns, since the assembler places
        # everything and components own their own internals.
        toolset("visual").subset(["component_search", "component_build", "typeset_check"]),
        Storyboard,
        max_iterations=10,
        agent_name="director",
    )
