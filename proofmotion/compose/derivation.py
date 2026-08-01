"""The derivation, once: understand, plan, verify, storyboard, map to scenes.

The studio grew its own trimmed copy of the pipeline's four-stage flow, and
the copies drifted — the studio's was silently missing the completeness retry
and the final-answer gate, so an opening question in the studio could ship a
deck that never states its answer. These are the steps themselves, free of
either caller's bookkeeping: the pipeline wraps them in stages and artifacts,
the studio in operations, and the gates run for both.
"""

from __future__ import annotations

from typing import Any

from proofmotion.runtime.events import headline


class IncompletePlan(Exception):
    """A plan or storyboard failed its completeness gate after one retry."""


def understood(client: Any, question: str, *, images: list[str] | None = None):
    from proofmotion.agents.intent import understand_request

    return understand_request(client, question, images=images)


def planned(
    client: Any,
    intent: Any,
    *,
    exam_requirements: dict[str, Any] | None = None,
    require_complete: bool = True,
    images: list[str] | None = None,
):
    """Derive the mathematics, and hold it to actually answering the question."""
    from proofmotion.agents.completeness import check_solution_completeness
    from proofmotion.agents.planner import plan_mathematics

    plan = plan_mathematics(client, intent, exam_requirements=exam_requirements, images=images)
    if not require_complete:
        return plan
    completeness = check_solution_completeness(plan, intent)
    if not completeness["complete"]:
        headline("Mathematical plan was incomplete; requesting a full worked solution", "warned")
        plan = plan_mathematics(
            client,
            intent,
            exam_requirements=exam_requirements,
            completion_feedback="; ".join(completeness["problems"]),
            images=images,
        )
        completeness = check_solution_completeness(plan, intent)
    if not completeness["complete"]:
        raise IncompletePlan(f"Mathematical plan is incomplete: {'; '.join(completeness['problems'])}")
    return plan


def verified(plan: Any) -> dict[str, Any]:
    from proofmotion.agents.verifier import verify_plan

    return verify_plan(plan)


def storyboarded(
    client: Any,
    intent: Any,
    plan: Any,
    verification: dict[str, Any],
    *,
    creator_brief: dict[str, Any] | None = None,
):
    """Design the scenes, and make sure the deck ends on the verified answer."""
    from proofmotion.agents.completeness import (
        check_storyboard_final_answer,
        ensure_storyboard_final_answer,
    )
    from proofmotion.agents.director import direct_storyboard

    storyboard = direct_storyboard(client, intent, plan, verification, creator_brief=creator_brief)
    complete = check_storyboard_final_answer(storyboard, plan.final_answer_latex)
    if not complete["complete"]:
        storyboard = ensure_storyboard_final_answer(
            storyboard, plan.final_answer_latex, plan.final_answer_explanation
        )
        complete = check_storyboard_final_answer(storyboard, plan.final_answer_latex)
        if not complete["complete"]:
            raise IncompletePlan(f"Storyboard is incomplete: {'; '.join(complete['problems'])}")
        headline("Added the verified final answer to the closing storyboard scene", "improved")
    return storyboard


def scene_plan_from(client: Any, state: dict[str, Any]):
    """Map the storyboard onto components, free when the director already did.

    The director has already searched for components and built them to check
    the geometry. When its storyboard names ones that validate, the plan is
    written and costs no further model call; the selector is only for when it
    does not.
    """
    from proofmotion.compose import plan_from_storyboard, select_components

    derived = plan_from_storyboard(state["storyboard"])
    if derived is not None:
        headline("Read the scene plan from the storyboard; no extra model call", "improved")
        return derived
    return select_components(client, state)["plan"]
