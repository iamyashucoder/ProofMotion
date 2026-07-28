"""Answer a question in full, the way the pipeline does, into a document.

The studio's edit agent is deliberately small — it answers "add a slide showing
24 rectangles" with one operation. Asked an opening question it did the same
thing, and one slide is not an explanation.

So an opening question runs the whole thing: read the request, derive the
mathematics with symbolic tools, verify it, storyboard it, and map every scene
onto a component. That is the pipeline that produced the good videos, and none
of it is rewritten here — it is the same four agents and the same derivation,
emitting operations instead of a render.

After that the deck exists and edits are edits. The expensive part happens once.
"""

from __future__ import annotations

import logging
from typing import Any

from proofmotion.compose import (
    ScenePlan,
    pictorial_coverage,
    plan_from_storyboard,
    select_components,
)
from proofmotion.layout.notation import readable
from proofmotion.runtime.events import headline
from proofmotion.studio.document import Project
from proofmotion.studio.operations import Operation

log = logging.getLogger(__name__)


def _plan_for(client: Any, question: str, state: dict[str, Any]) -> ScenePlan | None:
    """Run the pipeline's understanding and planning, and map it onto components."""
    from proofmotion.agents.director import direct_storyboard
    from proofmotion.agents.intent import understand_request
    from proofmotion.agents.planner import plan_mathematics
    from proofmotion.agents.verifier import verify_plan

    headline("Reading the request")
    intent = understand_request(client, question)
    state["intent"] = intent.model_dump()
    headline(f"Read it as: {intent.topic} ({intent.domain})")

    if not intent.requires_derivation:
        # Not every request is a problem to be solved. "Make a circle morph out
        # of a square" has nothing to derive, and deriving anyway produced
        # eight verified steps about superellipses and ten slides, none of
        # which drew anything. The intent agent already answers this; nobody
        # was reading its answer.
        headline("Nothing to derive here — going straight to the scenes")
        return None

    headline("Deriving the mathematics")
    plan = plan_mathematics(client, intent)
    state["math_plan"] = plan.model_dump()
    headline(f"Derived {len(plan.concept_sequence)} steps using symbolic tools", "improved")

    headline("Verifying")
    verification = verify_plan(plan)
    state["verified_math"] = verification
    failures = len(verification.get("failures") or [])
    headline(
        f"{len(plan.concept_sequence)} steps checked"
        + (f"; {failures} could not be proved" if failures else ""),
        "warned" if failures else "improved",
    )

    headline("Designing the scenes")
    storyboard = direct_storyboard(client, intent, plan, verification)
    state["storyboard"] = storyboard.model_dump()
    headline(f"Composed {len(storyboard.scenes)} scenes", "improved")

    # The director already searched for components and built them to check the
    # geometry. When its storyboard names ones that validate, the plan is
    # written and costs no further model call.
    derived = plan_from_storyboard(state["storyboard"])
    if derived is not None:
        headline("Read the scene plan from the storyboard; no extra model call", "improved")
        return derived

    headline("Choosing components for each scene")
    selection = select_components(client, state)
    return selection["plan"]


def _usable_assignment(assignment):
    """Fix the one mapping a component will refuse outright.

    equation_chain morphs one expression into the next and needs at least two
    to do it. A scene carrying a single equation was still being mapped onto it,
    and the component rejected every one — the slides simply went missing, with
    a pydantic error where the mathematics should have been. A lone equation is
    a caption, so it becomes one.
    """
    if assignment.component != "equation_chain":
        return assignment
    steps = [s for s in (assignment.parameters.get("steps") or []) if str(s).strip()]
    if len(steps) >= 2:
        return assignment
    return assignment.model_copy(update={
        "component": None,
        "parameters": {},
        "caption": assignment.caption or (steps[0] if steps else ""),
    })


def answer_fully(client: Any, project: Project, question: str) -> tuple[list[Operation], str]:
    """Turn an opening question into a deck, as operations.

    Returns the operations and a sentence for the person. Operations rather
    than slides so that one path builds the document: the same validation, the
    same ids, the same cache.
    """
    state: dict[str, Any] = {}
    try:
        plan = _plan_for(client, question, state)
    except Exception as error:
        log.exception("full answer failed")
        return [], f"I could not plan that: {error}"

    if plan is None or not plan.assignments:
        return [], "I could not turn that into scenes. Try describing what should be on screen."

    drawn = pictorial_coverage(plan)
    if drawn == 0:
        # Every scene is words. The pipeline sends this to the coder; here there
        # is no coder, so say so rather than delivering a deck of equations to
        # someone who asked to be shown something.
        headline("Nothing in this plan draws a picture", "warned")

    after = project.slides[-1].id if project.slides else ""
    operations = []
    for assignment in map(_usable_assignment, plan.assignments):
        operations.append(
            Operation(
                kind="add",
                after=after,
                title=assignment.title,
                component=assignment.component,
                parameters=assignment.parameters,
                caption=assignment.caption,
                seconds=assignment.seconds,
                reason="from the verified plan",
            )
        )
        after = ""  # the rest append in order

    return operations, written_answer(state, len(operations), drawn)


def written_answer(state: dict[str, Any], slides: int, drawn: float) -> str:
    """The worked solution, in words, for the conversation.

    The deck is the answer for someone watching it. Someone reading the chat
    got "built 11 slides", which is a receipt rather than a reply — the
    reasoning had been derived, verified and then thrown away because only the
    renderer was looking at it.
    """
    plan = state.get("math_plan") or {}
    steps = plan.get("concept_sequence") or []
    lines: list[str] = []

    given = plan.get("given_quantities") or []
    if given:
        lines.append("Given: " + ", ".join(str(g) for g in given))
    if plan.get("unknown"):
        lines.append(f"Find: {plan['unknown']}")
    if lines:
        lines.append("")

    for step in steps:
        head = f"{step.get('index', '?')}. {step.get('concept', '')}".strip()
        lines.append(head)
        equation = step.get("equation_latex")
        if equation:
            lines.append(f"   {readable(equation)}")
        explanation = (step.get("explanation") or "").strip()
        if explanation:
            lines.append(f"   {explanation}")
        lines.append("")

    answer = plan.get("final_answer_latex")
    if answer:
        lines.append(f"Answer: {readable(answer)}")
    if plan.get("final_answer_explanation"):
        lines.append(plan["final_answer_explanation"].strip())

    verification = state.get("verified_math") or {}
    failures = len(verification.get("failures") or [])
    lines.append("")
    note = f"{len(steps)} steps, {slides} slides"
    if failures:
        note += f" — {failures} step(s) sympy could not prove"
    if drawn < 1:
        note += f" — {drawn:.0%} of slides draw a figure"
    lines.append(note)
    return "\n".join(lines).strip()


def draw_by_hand(client: Any, question: str, seconds: int = 12) -> tuple[list[Operation], str]:
    """Have the coder write a scene when nothing in the catalogue fits.

    The studio composes components, and a catalogue is finite. Asked to animate
    a square morphing into a circle it searched, found nothing, and honestly
    said so — delivering no slides at all, for a request the pipeline it
    replaced would simply have drawn.

    So the coder comes back for exactly that case. The slide carries its own
    scene, renders like any other clip, and is cached like any other clip.
    """
    from proofmotion.agents.coder import write_scene

    headline("Nothing in the catalogue fits; writing the scene by hand")
    written = write_scene(
        client,
        {
            "intent": {"topic": question, "duration_seconds": seconds},
            "storyboard": {"scenes": [{"purpose": question, "duration_seconds": seconds}]},
        },
    )
    code = written.get("code") or ""
    if not code.strip():
        return [], "I could not draw that. Try describing what should be on screen."

    report = written.get("validation") or {}
    if not report.get("valid", True):
        problems = report.get("problems") or [{}]
        headline(f"The scene has {len(problems)} invalid API call(s)", "warned")

    return [Operation(
        kind="add",
        title=question[:56],
        seconds=float(seconds),
        code=code,
        reason="written by hand; no component fits",
    )], "Nothing in the catalogue fits, so I wrote the scene. Tell me what to change."
