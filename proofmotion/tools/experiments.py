"""Deterministic tools for explaining measured experiments and formal proofs."""

from __future__ import annotations

import math
from typing import Any, Literal

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

from proofmotion.runtime.registry import ToolError, tool


@tool
def measurement_line_fit(
    x_values: list[float], y_values: list[float], x_quantity: str = "x", y_quantity: str = "y"
) -> dict[str, Any]:
    """Fit measured data to a straight line and report graph-ready evidence.

    Use for Ohm's law, Hooke's law, pendulum graphs, photoelectric-effect
    plots, and any experiment whose slope has physical meaning.

    Args:
        x_values: Measured horizontal-axis values.
        y_values: Measured vertical-axis values at the same observations.
        x_quantity: Label for the horizontal measured quantity.
        y_quantity: Label for the vertical measured quantity.
    """
    if len(x_values) != len(y_values) or len(x_values) < 2:
        raise ToolError("x_values and y_values must have the same length of at least 2")
    if not all(math.isfinite(value) for value in [*x_values, *y_values]):
        raise ToolError("measurements must be finite numbers")
    count = len(x_values)
    mean_x, mean_y = sum(x_values) / count, sum(y_values) / count
    spread_x = sum((value - mean_x) ** 2 for value in x_values)
    if spread_x == 0:
        raise ToolError("x_values cannot all be equal; a slope cannot be measured")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(x_values, y_values)) / spread_x
    intercept = mean_y - slope * mean_x
    fitted = [slope * x + intercept for x in x_values]
    residuals = [y - predicted for y, predicted in zip(y_values, fitted)]
    total = sum((y - mean_y) ** 2 for y in y_values)
    residual_sum = sum(residual * residual for residual in residuals)
    r_squared = 1.0 if total == 0 and residual_sum == 0 else max(0.0, 1 - residual_sum / total)
    return {
        "model": f"{y_quantity} = ({slope:.8g}) {x_quantity} + ({intercept:.8g})",
        "slope": slope,
        "intercept": intercept,
        "r_squared": r_squared,
        "points": [
            {"x": x, "y": y, "fitted_y": predicted, "residual": residual}
            for x, y, predicted, residual in zip(x_values, y_values, fitted, residuals)
        ],
        "interpretation": "The slope is the measured proportionality constant; show residuals before claiming a linear law.",
    }


@tool
def propagate_measurement_uncertainty(
    expression: str, values: dict[str, float], uncertainties: dict[str, float]
) -> dict[str, Any]:
    """Propagate independent first-order measurement uncertainties.

    Args:
        expression: Result expression in Python/SymPy notation, e.g. "4*pi**2*L/T**2".
        values: Central measured values keyed by variable name.
        uncertainties: Absolute one-sigma uncertainty for every variable in values.
    """
    if set(values) != set(uncertainties):
        raise ToolError("values and uncertainties must contain exactly the same variable names")
    if any(error < 0 for error in uncertainties.values()):
        raise ToolError("uncertainties must be non-negative")
    symbols = {name: sp.Symbol(name) for name in values}
    try:
        expr = parse_expr(expression, local_dict=symbols, evaluate=True)
        central = float(expr.subs(symbols | values))
        terms = {
            name: float(sp.diff(expr, symbol).subs(symbols | values)) * uncertainties[name]
            for name, symbol in symbols.items()
        }
    except (TypeError, ValueError, SyntaxError) as error:
        raise ToolError(f"could not evaluate uncertainty for {expression!r}: {error}") from error
    absolute = math.sqrt(sum(term * term for term in terms.values()))
    return {
        "expression": expression,
        "value": central,
        "absolute_uncertainty": absolute,
        "relative_uncertainty": None if central == 0 else abs(absolute / central),
        "contributions": {name: abs(term) for name, term in terms.items()},
        "assumption": "independent small uncertainties; first-order propagation",
    }


@tool
def proof_obligations(
    claim: str,
    method: Literal["direct", "contrapositive", "contradiction", "induction", "construction", "invariant"],
    assumptions: list[str],
) -> dict[str, Any]:
    """Return the non-negotiable checks a mathematical proof must visibly satisfy.

    Args:
        claim: Exact statement to prove.
        method: Valid proof method to structure the explanation.
        assumptions: Definitions, domains, and given premises allowed in the proof.
    """
    common = [
        "State the claim, definitions, and domain restrictions.",
        "Use only stated assumptions or established results.",
        "Justify every implication; a diagram gives intuition but is never proof.",
        "Restate exactly the requested claim and its conditions.",
    ]
    by_method = {
        "direct": ["Start from the assumptions and derive the conclusion in ordered implications."],
        "contrapositive": ["Prove not-conclusion implies not-hypothesis, then state logical equivalence."],
        "contradiction": ["Assume the negation, derive an explicit contradiction, then discharge the assumption."],
        "induction": ["Prove a base case, state the induction hypothesis, prove k -> k+1, then conclude for the stated range."],
        "construction": ["Define the object and prove every required property; prove uniqueness separately if claimed."],
        "invariant": ["Name the invariant, prove it initially and after every operation, then apply it to the final state."],
    }
    return {"claim": claim, "method": method, "assumptions": assumptions, "obligations": [*common, *by_method[method]]}
