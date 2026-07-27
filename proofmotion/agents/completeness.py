"""Hard gates for a worked solution before any animation is allowed to start."""

from __future__ import annotations

from proofmotion.tools.typeset import typeset_check
from schemas.intent import AnimationIntent
from schemas.math_plan import MathematicalPlan


def _normalise_equation(value: str) -> str:
    return "".join(value.replace(r"\boxed", "").replace("{", "").replace("}", "").split())


def check_solution_completeness(plan: MathematicalPlan, intent: AnimationIntent) -> dict[str, object]:
    """Reject plans that visualise a topic but do not solve the asked problem."""
    problems: list[str] = []
    if not plan.final_answer_latex or not plan.final_answer_latex.strip():
        problems.append("missing final_answer_latex")
    elif not typeset_check(plan.final_answer_latex, engine="latex")["valid"]:
        problems.append("final_answer_latex does not typeset")
    if not plan.final_answer_explanation or not plan.final_answer_explanation.strip():
        problems.append("missing final_answer_explanation")
    if intent.requires_derivation and len(plan.concept_sequence) < 3:
        problems.append("a requested derivation needs at least three explicit mathematical steps")
    if intent.requires_derivation and not plan.given_quantities:
        problems.append("missing given_quantities for the worked problem")
    if intent.requires_derivation and not plan.unknown:
        problems.append("missing unknown for the worked problem")
    if intent.requires_derivation and not plan.governing_principles:
        problems.append("missing governing_principles for the worked problem")
    if not any(step.equation_latex for step in plan.concept_sequence):
        problems.append("the plan contains no displayed mathematical calculation")
    elif plan.final_answer_latex:
        final_step = next((step.equation_latex for step in reversed(plan.concept_sequence) if step.equation_latex), "")
        answer = _normalise_equation(plan.final_answer_latex)
        derived = _normalise_equation(final_step)
        if answer not in derived and derived not in answer:
            problems.append("final_answer_latex does not match the last derived equation")
    return {"complete": not problems, "problems": problems}


def check_storyboard_final_answer(storyboard: object, final_answer_latex: str | None) -> dict[str, object]:
    """Require a visible, dedicated final-answer scene before coding starts."""
    if not final_answer_latex:
        return {"complete": False, "problems": ["no verified final answer is available for the storyboard"]}
    scenes = getattr(storyboard, "scenes", [])
    visible = any(final_answer_latex in getattr(scene, "equations", []) for scene in scenes)
    final_scene = any("final answer" in getattr(scene, "title", "").lower() for scene in scenes)
    problems = []
    if not visible:
        problems.append("the verified final answer is absent from storyboard equations")
    if not final_scene:
        problems.append("the storyboard has no scene titled FINAL ANSWER")
    return {"complete": not problems, "problems": problems}
