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

For a matrices problem, use matrix_arithmetic for products or sums,
matrix_row_operation for every displayed elementary operation,
matrix_linear_system for AX=B, and matrix_properties for determinant,
adjugate, inverse, symmetry, or Cayley-Hamilton claims. Pair a 2x2 numerical
linear map with the matrix_transform visual component whenever geometry helps.
For determinants, show a cofactor expansion with determinant_cofactor_expansion,
track every row-operation effect with determinant_row_effect, solve parameter
questions with determinant_parameter_solve, and use determinant_signed_area
with matrix_transform when orientation or area is relevant.
For 3D geometry, compute every line/plane relation with the three_d_* tools
before drawing it. Use the vector_plane_3d component for a clear labelled
diagram, show the normal and direction vectors, and distinguish parallel,
intersecting, coincident, and skew cases explicitly.
For complex-number problems, use complex_number_analysis and
complex_number_operation for every displayed value, complex_polynomial_roots
or roots_of_unity for roots, and complex_locus for locus claims. Use
complex_plane_vector or roots_of_unity_polygon to keep the algebra tied to an
Argand-plane diagram.
For calculus, do not turn a complete solution into a bare derivative or an
unexplained graph. Use calculus_limit_continuity for every continuity claim,
calculus_curve_analysis for stationary/inflection analysis, and
calculus_tangent_normal for each displayed tangent or normal. Use
calculus_definite_integral for a definite value and calculus_area_between_curves
when the word "area" means geometric area. Use calculus_taylor_approximation
for series approximations, calculus_parametric_analysis for parametric motion,
calculus_multivariable_analysis for gradients/Hessians, and
calculus_autonomous_ode plus numeric_ode for phase-line or trajectory claims.
Match them to limit_approach, function_plot, tangent_secant, riemann_area,
area_between_curves, taylor_comparison, or vector_field so the visual confirms
the computation rather than decorating it.
For coordinate geometry, use coordinate_line_analysis for every line relation,
coordinate_circle_analysis for a general circle and tangent/normal, and
coordinate_conic_classify before naming a general quadratic conic. Use
coordinate_triangle_centres, coordinate_section_formula, coordinate_transform,
and coordinate_locus_ratio for their respective results. Then select the
matching coordinate_line_pair, circle_coordinate_diagram,
conic_coordinate_diagram, coordinate_triangle_centres, or
coordinate_transformation component. Never infer an intersection, centre, or
locus merely from a diagram.
For the standard hyperbola whose latus rectum subtends a right angle at the
opposite focus, call hyperbola_latus_rectum_right_angle with c before writing
any derivation. Its alpha, beta, and alpha_plus_beta are exact computed values;
copy them unchanged and show its right-angle and focus-relation checks.
For trigonometry, call trig_exact_values instead of approximating a standard
angle, trig_identity_check before asserting an identity, and trig_equation_solve
with the requested degree interval for every equation. Use
trig_inverse_principal to state the principal branch, and the sine/cosine rule
tools for non-right triangles. Pair the verified result with unit_circle,
trig_triangle, or trig_wave; degrees and radians must be visible before values
are substituted.

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
