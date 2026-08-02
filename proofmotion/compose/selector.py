"""Decide which component expresses each scene.

This is the only judgement left in the assembly path, and it is the one the
model is actually good at: reading a storyboard beat and recognising that it is
a Riemann sum. Everything downstream — placement, reveal order, clearing the
stage — is emitted by the assembler, so a wrong answer here costs a fallback to
the coder rather than a broken video.

Returning null for a scene is a supported answer, and a cheap one. Forcing a
component onto a scene it does not fit produces a confidently wrong picture,
which is worse than hand-written code.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from proofmotion.compose.assembler import ScenePlan, check, coverage
from proofmotion.compose.shapes import SHAPE_FIRST
from proofmotion.tools.components_tool import catalogue_text
from proofmotion.runtime.loop import run_structured
from proofmotion.tools import toolset

log = logging.getLogger(__name__)

SYSTEM = f"""You map a storyboard onto verified components.

Components are tested builders that own the hard parts — axis ranges derived
from the actual function, label positions scored against the geometry, text
fitted to its region. For each scene, decide which single component expresses
it, and with what parameters.

Call component_search first — it returns each component's exact parameters along
with what it is for. Ask for several searches in one turn; they run concurrently.

{SHAPE_FIRST}

Give real parameters, computed from the verified plan you are given — the actual
function, the actual interval, the actual values. Not placeholders.

Then call component_build on each choice to check it. It builds the real
geometry and measures it, so a crowded range or an off-frame curve comes back as
a collision count rather than as a defect in the finished video. Fix the
parameters and build again until it reports ok.

A scene with no picture in it — a derivation, a rearrangement, a substitution —
is not a scene without a component. That is what equation_chain is for: give it
the steps as LaTeX and it morphs each into the next. Reach for it before you
conclude a scene cannot be composed — and a scene that compares, decomposes,
stacks or tabulates is a shape component before it is equation_chain.

Answer null for a scene's component only when nothing genuinely fits — a
construction no component covers. Then give the scene a title and a caption, so
it still has something to show. A component forced onto a scene it does not fit
draws something confidently wrong, which is worse than leaving it null.

Keep the caption to the one equation the scene is about, as LaTeX without $
delimiters, or leave it empty. Titles are short — a few words, not a sentence.
Give each scene narration — a sentence or two that reads aloud what the viewer
is watching. It is spoken, never shown on screen.

Scene lengths should sum to roughly the target duration in the brief."""


def select_components(
    client: Any, context: dict[str, Any], *, max_iterations: int = 6
) -> dict[str, Any]:
    """Map the storyboard onto components, or report that it cannot be done.

    Never raises: an unusable plan is a normal outcome that sends the run down
    the coder path, and the caller should not have to distinguish a failed
    selection from a broken one.
    """
    target = int((context.get("intent") or {}).get("duration_seconds") or 30)
    brief = json.dumps(
        {
            "intent": context.get("intent"),
            "verified_plan": context.get("math_plan"),
            "storyboard": context.get("storyboard"),
            "computed_values": context.get("tool_results"),
            "target_seconds": target,
        },
        indent=2,
        default=str,
    )
    try:
        plan = run_structured(
            client,
            SYSTEM,
            f"{catalogue_text()}\n\nMap this storyboard onto components.\n\n{brief}",
            toolset("visual").subset(["component_search", "component_build"]),
            ScenePlan,
            max_iterations=max_iterations,
            max_tokens=6000,
            agent_name="selector",
        )
    except Exception as error:  # noqa: BLE001 - the coder path is the fallback
        log.info("component selection unavailable, coder will write the scene: %s", error)
        return {"plan": None, "coverage": 0.0, "problems": [str(error)[:300]]}

    problems = check(plan)
    return {
        "plan": plan,
        "coverage": coverage(plan),
        "problems": problems,
        "components": [a.component for a in plan.assignments if a.component],
    }
