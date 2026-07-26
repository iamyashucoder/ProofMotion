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

Clear the stage. Every scene must say what leaves the screen as well as what
arrives — a title or equation left behind gets drawn over by the next one, and
the result reads as garbled text rather than as two things. If a scene keeps
something from the previous one, say so explicitly; otherwise assume it goes.

Use only scenes that teach something new, but do not compress an explanation
just to meet an arbitrary runtime target.

Measure before you place. layout_measure tells you how much room a piece of
text or maths will occupy; layout_frame tells you the usable area; layout_check
tells you whether a planned arrangement overlaps or falls off the edge. Use
them. Overlapping labels are the most common defect in generated animations and
they come entirely from assuming rather than measuring.

Confirm every equation typesets with typeset_check before putting it in a scene.

Every storyboard must reserve: (1) a compact question card in a safe corner,
(2) clear space for the main visual, and (3) a final scene titled `FINAL
ANSWER` that states only the verified result. For graph, axes, vector, or
geometry scenes, specify a turtle carrying a marker that progressively draws
the visible mathematical strokes. Write notation as typeset maths, not prose
Text, so roots, logs, fractions, and modular arithmetic remain readable.

For every textual or mathematical object, measure it against the safe frame.
If it does not fit, instruct the coder to scale the existing object to fit; if
that would make it unreadable, put it in a separate beat rather than overlap it.

Use a bright high-contrast palette: a lighter deep-indigo background with
white/light labels and vivid accents. Avoid a near-black scene or dim objects.

Give each scene a purpose, a duration proportional to how much there is to read,
and narration that would make sense read aloud."""

BEGINNER_ADDENDUM = """
Beginner mode is active. Start with a visual meaning before algebra. Every scene
must add one short plain-language caption (at most 12 words) that explains the
new idea, and must define a new symbol on its first appearance. Use one equation
transformation per beat. Do not make the viewer infer why a derivative is being
taken: say that velocity means how position changes and acceleration means how
velocity changes. Prefer three or four scenes over a dense single derivation.
Do not show `FINAL ANSWER` until the final 15% of the video. Spend the earlier
time making the question feel inevitable: show the setup, state what each
symbol means, animate each transformation, and add a short caption explaining
why the transformation is valid.
"""


def direct_storyboard(
    client: Any,
    intent: AnimationIntent,
    plan: MathematicalPlan,
    verification: dict[str, Any],
    user_question: str,
) -> Storyboard:
    """Compose a storyboard from the verified plan."""
    steps = "\n".join(
        f"  {s.index}. {s.concept}: {s.equation_latex or '(prose)'} — {s.explanation}"
        for s in plan.concept_sequence
    )
    prompt = (
        f"Topic: {intent.topic}\n"
        f"Original user question: {user_question}\n"
        f"Audience: {intent.audience} ({intent.difficulty})\n"
        f"Goal: {intent.educational_goal}\n"
        "Use as many scenes and beats as needed for the viewer to understand.\n"
        f"Mathematics verified: {verification['valid']}\n\n"
        f"Verified steps:\n{steps}\n\n"
        + (BEGINNER_ADDENDUM if intent.audience == "beginner" or intent.difficulty == "introductory" else "")
        + "Design the storyboard."
    )
    return run_structured(
        client,
        SYSTEM,
        prompt,
        toolset("visual"),
        Storyboard,
        max_iterations=10,
        agent_name="director",
    )
