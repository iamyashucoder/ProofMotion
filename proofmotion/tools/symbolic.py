"""Symbolic mathematics. The source of truth for every claim an animation makes.

Domain-general by construction: nothing here knows what "gradient descent" is.
An agent that wants a derivative asks for a derivative.
"""

from __future__ import annotations

from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

from proofmotion.runtime.registry import ToolError, tool


def _parse(expression: str) -> sp.Expr:
    try:
        return parse_expr(expression, evaluate=True)
    except (SyntaxError, TypeError, ValueError, AttributeError) as error:
        raise ToolError(f"Could not parse {expression!r} as a mathematical expression: {error}") from error


def _render(expr: Any) -> dict[str, Any]:
    return {"result": str(expr), "latex": sp.latex(expr)}


@tool
def symbolic_differentiate(expression: str, variable: str = "x", order: int = 1) -> dict[str, Any]:
    """Differentiate an expression symbolically.

    Args:
        expression: e.g. "(x-2)**2 + 1" or "sin(x)*exp(x)".
        variable: Variable to differentiate with respect to.
        order: Order of the derivative.
    """
    result = sp.diff(_parse(expression), sp.Symbol(variable), order)
    return {"input": expression, "variable": variable, "order": order, **_render(result)}


@tool
def symbolic_integrate(expression: str, variable: str = "x", lower: str = "", upper: str = "") -> dict[str, Any]:
    """Integrate an expression, definitely when bounds are given.

    Args:
        expression: Integrand, e.g. "x**2".
        variable: Variable of integration.
        lower: Optional lower bound; give both bounds for a definite integral.
        upper: Optional upper bound.
    """
    expr, symbol = _parse(expression), sp.Symbol(variable)
    if lower and upper:
        result = sp.integrate(expr, (symbol, _parse(lower), _parse(upper)))
        return {"input": expression, "definite": True, "bounds": [lower, upper], **_render(result)}
    return {"input": expression, "definite": False, **_render(sp.integrate(expr, symbol))}


@tool
def symbolic_simplify(expression: str) -> dict[str, Any]:
    """Simplify an expression to a canonical form.

    Args:
        expression: e.g. "(x**2 - 1)/(x - 1)".
    """
    return {"input": expression, **_render(sp.simplify(_parse(expression)))}


@tool
def symbolic_solve(equation: str, variable: str = "x") -> dict[str, Any]:
    """Solve an equation or expression for a variable.

    Args:
        equation: Either "x**2 - 4" (implicitly = 0) or "x**2 = 4".
        variable: Variable to solve for.
    """
    if "=" in equation:
        left, _, right = equation.partition("=")
        expr = _parse(left) - _parse(right)
    else:
        expr = _parse(equation)
    solutions = sp.solve(expr, sp.Symbol(variable), dict=False)
    return {
        "equation": equation,
        "variable": variable,
        "solutions": [str(s) for s in solutions],
        "latex": [sp.latex(s) for s in solutions],
    }


@tool
def symbolic_limit(expression: str, variable: str = "x", approaching: str = "0", side: str = "+-") -> dict[str, Any]:
    """Evaluate a limit.

    Args:
        expression: e.g. "sin(x)/x".
        variable: The variable that moves.
        approaching: Target value; "oo" for infinity.
        side: "+", "-", or "+-" for two-sided.
    """
    direction = side if side in {"+", "-"} else "+-"
    result = sp.limit(_parse(expression), sp.Symbol(variable), _parse(approaching), direction)
    return {"input": expression, "approaching": approaching, **_render(result)}


@tool
def symbolic_series(expression: str, variable: str = "x", around: str = "0", order: int = 6) -> dict[str, Any]:
    """Taylor/Laurent expansion of an expression.

    Args:
        expression: e.g. "exp(x)".
        variable: Expansion variable.
        around: Point to expand about.
        order: Number of terms before the O() remainder.
    """
    result = sp.series(_parse(expression), sp.Symbol(variable), _parse(around), order)
    return {"input": expression, "around": around, "order": order, **_render(result)}


@tool
def symbolic_verify_equality(left: str, right: str, variable: str = "x", samples: int = 12) -> dict[str, Any]:
    """Check whether two expressions are mathematically equal.

    The core verification primitive. Numeric sampling runs first because it
    refutes a false claim quickly; symbolic simplification then decides the
    survivors. A claim is only reported proved when simplify reaches zero.

    Args:
        left: Left-hand expression.
        right: Right-hand expression.
        variable: Free variable to sample over.
        samples: How many random points to test before simplifying.
    """
    import random

    lhs, rhs, symbol = _parse(left), _parse(right), sp.Symbol(variable)
    difference = sp.simplify(lhs - rhs)

    rng = random.Random(0)
    counterexample = None
    for _ in range(samples):
        point = rng.uniform(-5, 5)
        try:
            gap = complex(difference.subs(symbol, point).evalf())
        except (TypeError, ValueError):
            continue
        if abs(gap) > 1e-8:
            counterexample = {"at": point, "difference": str(gap)}
            break

    equal = counterexample is None and difference == 0
    return {
        "left": left,
        "right": right,
        "equal": bool(equal),
        "difference": str(difference),
        "counterexample": counterexample,
        "method": "sympy.simplify + numeric sampling",
    }
