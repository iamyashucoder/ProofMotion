"""Check the plan's mathematics against tools rather than against belief.

The agent this replaces validated LaTeX by counting braces and had a single
`if plan.topic == "gradient descent"` branch that did one real check. This is
deterministic: no model is asked whether the mathematics is right.
"""

from __future__ import annotations

from tokenize import TokenError
from typing import Any

from proofmotion.runtime.registry import ToolError
from proofmotion.tools.reasoning import counterexample_search
from proofmotion.tools.symbolic import symbolic_verify_equality
from proofmotion.tools.typeset import typeset_check
from schemas.math_plan import MathematicalPlan


def _check_equation(latex: str) -> dict[str, Any]:
    """Typeset the equation, and verify it when it states an equality."""
    result: dict[str, Any] = {"equation_latex": latex}
    typeset = typeset_check(latex, engine="latex")
    result["typesets"] = typeset["valid"]
    if not typeset["valid"]:
        result["error"] = typeset.get("error")
        return result

    # A single '=' is a claim we can actually test; anything else is notation.
    body = latex.replace("\\,", " ").replace("\\!", "")
    if body.count("=") == 1 and not any(t in body for t in ("\\lim", "\\int", "\\sum", "\\to", "\\approx")):
        left, _, right = body.partition("=")
        try:
            # Normalise through the implicit-multiplication parser first, so
            # "2x" reaches sympy as 2*x rather than as a syntax error.
            lhs, rhs = str(_parse_math(_to_sympy(left))), str(_parse_math(_to_sympy(right)))
            equality = symbolic_verify_equality(lhs, rhs)
            result["kind"] = "checked equality"
            result["equal"] = equality["equal"]
            result["counterexample"] = equality["counterexample"]
            if equality["equal"]:
                # Sampling can refute what simplify quietly accepted, so the
                # cheaper refutation runs as a second opinion rather than a first.
                refutation = counterexample_search(f"{lhs} = {rhs}", samples=80)
                if refutation["refuted"]:
                    result["equal"] = False
                    result["counterexample"] = refutation["counterexample"]
                    result["kind"] = "refuted by sampling"
        except (ToolError, ValueError, TypeError, SyntaxError, TokenError) as error:
            result["kind"] = "not mechanically checkable"
            result["note"] = str(error)[:200]
    else:
        result["kind"] = "notation or limit statement"
    return result


def _to_sympy(latex: str) -> str:
    """Best-effort LaTeX to sympy text for the subset that appears in equations.

    Mathematics writes 2x where Python demands 2*x, so a true identity such as
    (x+1)^2 = x^2+2x+1 previously came back "not mechanically checkable" — the
    conversion, not the mathematics, was the obstacle. Implicit multiplication is
    restored below by sympy's own transformation.
    """
    text = latex.strip().strip("$ ")
    for tex, plain in (
        (r"\left", ""), (r"\right", ""), (r"\cdot", "*"), (r"\times", "*"),
        (r"\,", " "), (r"\!", ""), (r"\;", " "),
        ("^", "**"), ("{", "("), ("}", ")"), ("\\", ""),
    ):
        text = text.replace(tex, plain)
    return text


def _parse_math(text: str):
    """Parse with implicit multiplication, the way the notation is written."""
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    return parse_expr(text, transformations=(*standard_transformations, implicit_multiplication_application))


def verify_plan(plan: MathematicalPlan) -> dict[str, Any]:
    """Verify every step that carries an equation. Deterministic, no LLM."""
    checks = []
    for step in plan.concept_sequence:
        if not step.equation_latex:
            checks.append({"step": step.index, "kind": "prose step", "typesets": True, "equal": None})
            continue
        checks.append({"step": step.index, **_check_equation(step.equation_latex)})

    failures = [
        check
        for check in checks
        if check.get("typesets") is False
        or check.get("equal") is False
        or check.get("kind") == "not mechanically checkable"
    ]
    return {
        "valid": not failures,
        "checks": checks,
        "failures": failures,
        "verified_by": "sympy + latex compilation",
    }
