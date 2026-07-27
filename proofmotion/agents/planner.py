"""Build the mathematical spine of the explanation.

Replaces hand-written MathStep lists, one per known topic. Steps are now derived
with the symbolic tools, so a derivative in the plan is a derivative sympy
computed rather than one someone typed.
"""

from __future__ import annotations

from typing import Any

from proofmotion.runtime.loop import run_structured
from proofmotion.tools import toolset
from schemas.intent import AnimationIntent
from schemas.math_plan import MathematicalPlan

SYSTEM = """You lay out the mathematical steps of an explanation, in teaching order.

Each step should carry one idea and connect to the one before it. Move from a
concrete instance to the general statement unless the audience is advanced.

Do not compress a derivation to fit an assumed duration. When the question asks
for a solution, show every mathematical transformation that is needed to reach
the requested unknown: identify the given quantities, select the governing
law, derive or rearrange it, substitute values, simplify, check units, and give
the final answer. A visual can support a calculation but can never replace it.
Always return final_answer_latex and final_answer_explanation after the
derivation; these must answer the requested unknown directly.
For a worked problem also return given_quantities, unknown, and
governing_principles before the concept_sequence.
The last mathematical step must derive the same equation as final_answer_latex;
do not introduce a new, unsupported result in the final answer.

Compute with the tools; do not do algebra in your head. The full surface is
available — linear algebra, differential equations, vector calculus, number
theory, combinatorics, logic, graphs, probability, statistics and analytic
geometry — so reach for the tool that matches the subject rather than reducing
everything to hand algebra. Derivatives, integrals,
limits, series, roots, and equality checks are all available, and their answers
are correct by construction. Every equation you write into the plan must be one
a tool returned or one you have checked with symbolic_verify_equality.

For a JEE Advanced, JEE Main, NEET, Olympiad, or competitive-exam request, call
competitive_exam_requirements before planning. Follow its required structure:
give the data and unknown, introduce a labelled diagram, make one justified
transformation per displayed step, substitute values with units, and only then
box the answer. Use jee_mechanics, stoichiometry_limit, ideal_gas_state, or weak_acid_ph
when the pattern fits, rather than estimating values from memory.

Refute before you assert. counterexample_search takes seconds and settles a
false claim outright; units_check catches a wrong physical formula whatever the
algebra says; limiting_case_check tells you whether a general result collapses to
the known answer. Run them on anything you are about to put on screen.

For an experimental explanation, compute a measurement_line_fit from the
observations before interpreting a graph. State the slope, intercept, residuals,
and what physical quantity the slope represents. When precision matters, use
propagate_measurement_uncertainty rather than claiming exact measurements. For
a proof, call proof_obligations first and visibly establish each obligation; a
picture supplies intuition but never replaces a proof.

Write LaTeX in equation_latex. State any assumption a step depends on — a
domain restriction, a convergence condition, a continuity requirement — because
these become the bounds on what the finished animation is allowed to claim."""


def plan_mathematics(
    client: Any,
    intent: AnimationIntent,
    exam_requirements: dict[str, Any] | None = None,
    completion_feedback: str | None = None,
) -> MathematicalPlan:
    """Derive a verified sequence of mathematical steps for the intent."""
    return run_structured(
        client,
        SYSTEM,
        (
            f"Topic: {intent.topic}\n"
            f"Field: {intent.domain}\n"
            f"Audience: {intent.audience} ({intent.difficulty})\n"
            f"Goal: {intent.educational_goal}\n"
            f"Assumptions so far: {intent.assumptions or 'none'}\n"
            f"Competitive-exam requirements: {exam_requirements or 'not a competitive-exam prompt'}\n"
            f"Completion feedback from a previous rejected plan: {completion_feedback or 'none'}\n\n"
            "Return final_answer_latex and final_answer_explanation in addition to the complete ordered derivation.\n\n"
            "Produce the mathematical plan."
        ),
        toolset("compute", "reason", "competitive", "evidence"),
        MathematicalPlan,
        max_iterations=10,
        agent_name="planner",
    )
