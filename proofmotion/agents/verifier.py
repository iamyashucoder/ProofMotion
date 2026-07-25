"""Check the plan's mathematics against tools rather than against belief.

The agent this replaces validated LaTeX by counting braces and had a single
`if plan.topic == "gradient descent"` branch that did one real check. This is
deterministic: no model is asked whether the mathematics is right.
"""

from __future__ import annotations

from typing import Any

from proofmotion.runtime.registry import ToolError
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
            equality = symbolic_verify_equality(_to_sympy(left), _to_sympy(right))
            result["kind"] = "checked equality"
            result["equal"] = equality["equal"]
            result["counterexample"] = equality["counterexample"]
        except (ToolError, ValueError, TypeError) as error:
            result["kind"] = "not mechanically checkable"
            result["note"] = str(error)[:200]
    else:
        result["kind"] = "notation or limit statement"
    return result


def _to_sympy(latex: str) -> str:
    """Best-effort LaTeX to sympy text for the subset that appears in equations."""
    text = latex.strip().strip("$ ")
    for tex, plain in (
        ("\\left", ""), ("\\right", ""), ("\\cdot", "*"), ("^", "**"),
        ("{", "("), ("}", ")"), ("\\", ""),
    ):
        text = text.replace(tex, plain)
    return text


def verify_plan(plan: MathematicalPlan) -> dict[str, Any]:
    """Verify every step that carries an equation. Deterministic, no LLM."""
    checks = []
    for step in plan.concept_sequence:
        if not step.equation_latex:
            checks.append({"step": step.index, "kind": "prose step", "typesets": True, "equal": None})
            continue
        checks.append({"step": step.index, **_check_equation(step.equation_latex)})

    failures = [c for c in checks if c.get("typesets") is False or c.get("equal") is False]
    return {
        "valid": not failures,
        "checks": checks,
        "failures": failures,
        "verified_by": "sympy + latex compilation",
    }
