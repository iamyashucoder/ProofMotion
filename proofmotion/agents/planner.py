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

Use as many focused steps as are needed to explain the idea. Prefer a worked
instance plus the general statement over exhaustive enumeration, but never
collapse essential reasoning merely to make the animation shorter.

Compute with the tools; do not do algebra in your head. The full surface is
available — linear algebra, differential equations, vector calculus, number
theory, combinatorics, logic, graphs, probability, statistics and analytic
geometry — so reach for the tool that matches the subject rather than reducing
everything to hand algebra. Derivatives, integrals,
limits, series, roots, and equality checks are all available, and their answers
are correct by construction. Every equation you write into the plan must be one
a tool returned or one you have checked with symbolic_verify_equality.

Refute before you assert. counterexample_search takes seconds and settles a
false claim outright; units_check catches a wrong physical formula whatever the
algebra says; limiting_case_check tells you whether a general result collapses to
the known answer. Run them on anything you are about to put on screen.

Write LaTeX in equation_latex. State any assumption a step depends on — a
domain restriction, a convergence condition, a continuity requirement — because
these become the bounds on what the finished animation is allowed to claim."""

BEGINNER_ADDENDUM = """
Beginner mode is active. Use enough small steps to teach, not merely to finish.
Before a symbol is used
in an equation, explain it in ordinary words: for example, x is position, v is
velocity (how position changes), and a is acceleration (how velocity changes).
Show one algebra move at a time; do not place a long quotient-rule derivation
on one line. Each explanation must be one or two short sentences with no
unintroduced jargon. Include: (1) the physical/intuitive picture, (2) symbol
definitions, (3) each derivation move, (4) why that move is allowed, and only
then (5) the final answer. The aim is understanding, not a compressed exam
solution.
"""


def plan_mathematics(client: Any, intent: AnimationIntent) -> MathematicalPlan:
    """Derive a verified sequence of mathematical steps for the intent."""
    prompt = (
        f"Topic: {intent.topic}\n"
        f"Field: {intent.domain}\n"
        f"Audience: {intent.audience} ({intent.difficulty})\n"
        f"Goal: {intent.educational_goal}\n"
        f"Assumptions so far: {intent.assumptions or 'none'}\n"
        "Use as many steps as are needed for a clear explanation. Do not reduce "
        "the derivation merely to fit an arbitrary video duration.\n\n"
        + (BEGINNER_ADDENDUM if intent.audience == "beginner" or intent.difficulty == "introductory" else "")
        + "Produce the mathematical plan."
    )
    return run_structured(
        client,
        SYSTEM,
        prompt,
        toolset("compute", "reason"),
        MathematicalPlan,
        max_iterations=10,
        agent_name="planner",
    )
