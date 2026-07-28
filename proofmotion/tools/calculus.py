"""Verified calculus workflows for complete solutions and visual planning.

The generic symbolic tools answer isolated questions.  These tools assemble the
related quantities an explanation needs: a limit includes its one-sided checks,
a curve sketch includes derivative tests, and a definite integral includes the
area interpretation.  Each result is computed by SymPy or NumPy; no final
quantity is guessed by the language model.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


def _parse(expression: str, locals_: dict[str, Any] | None = None) -> sp.Expr:
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    try:
        return parse_expr(
            expression,
            local_dict=locals_ or {},
            transformations=(*standard_transformations, implicit_multiplication_application),
        )
    except (SyntaxError, TypeError, ValueError, AttributeError) as error:
        raise ToolError(f"could not parse {expression!r}: {error}") from error


def _render(value: Any) -> dict[str, str]:
    return {"result": str(value), "latex": sp.latex(value)}


def _real_solutions(expression: sp.Expr, symbol: sp.Symbol) -> list[sp.Expr]:
    try:
        found = sp.solveset(expression, symbol, domain=sp.S.Reals)
        if isinstance(found, sp.FiniteSet):
            return sorted(found, key=lambda item: float(sp.N(item)))
    except (TypeError, ValueError, NotImplementedError):
        pass
    return []


@tool
def calculus_curve_analysis(expression: str, variable: str = "x") -> dict[str, Any]:
    """Analyse a one-variable curve for a graph sketch and derivative proof.

    Returns the domain, first and second derivatives, stationary points,
    inflection candidates, and intercepts.  Classification is only reported
    when the second-derivative test is decisive.
    """
    x = sp.Symbol(variable, real=True)
    expr = _parse(expression, {variable: x})
    first, second = sp.simplify(sp.diff(expr, x)), sp.simplify(sp.diff(expr, x, 2))
    stationary = _real_solutions(first, x)
    inflections = _real_solutions(second, x)
    classified = []
    for point in stationary:
        test = sp.simplify(second.subs(x, point))
        kind = "inconclusive"
        if test.is_positive:
            kind = "local minimum"
        elif test.is_negative:
            kind = "local maximum"
        classified.append({
            "x": str(point), "x_latex": sp.latex(point),
            "y": str(sp.simplify(expr.subs(x, point))),
            "second_derivative": str(test), "classification": kind,
        })
    return {
        "expression": expression,
        "domain": str(sp.calculus.util.continuous_domain(expr, x, sp.S.Reals)),
        "first_derivative": _render(first),
        "second_derivative": _render(second),
        "stationary_points": classified,
        "inflection_candidates": [{"x": str(p), "y": str(sp.simplify(expr.subs(x, p)))} for p in inflections],
        "x_intercepts": [str(root) for root in _real_solutions(expr, x)],
        "y_intercept": str(sp.simplify(expr.subs(x, 0))),
        "visual": "function_plot + tangent_secant + derivative_sign_chart",
    }


@tool
def calculus_limit_continuity(
    expression: str, point: str, variable: str = "x"
) -> dict[str, Any]:
    """Check both one-sided limits, function value, and continuity at a point."""
    x = sp.Symbol(variable, real=True)
    expr, at = _parse(expression, {variable: x}), _parse(point, {variable: x})
    left, right = sp.limit(expr, x, at, "-"), sp.limit(expr, x, at, "+")
    two_sided = sp.limit(expr, x, at) if sp.simplify(left - right) == 0 else sp.nan
    try:
        value = sp.simplify(expr.subs(x, at))
    except (TypeError, ValueError):
        value = sp.nan
    continuous = bool(two_sided != sp.nan and value != sp.nan and sp.simplify(two_sided - value) == 0)
    return {
        "expression": expression, "point": point,
        "left_limit": _render(left), "right_limit": _render(right),
        "two_sided_limit": _render(two_sided), "function_value": _render(value),
        "continuous": continuous,
        "classification": "continuous" if continuous else "discontinuous or undefined",
        "visual": "limit_approach",
    }


@tool
def calculus_tangent_normal(
    expression: str, at: str, variable: str = "x"
) -> dict[str, Any]:
    """Compute exact tangent and normal lines at a point of a curve."""
    x = sp.Symbol(variable, real=True)
    expr, x0 = _parse(expression, {variable: x}), _parse(at, {variable: x})
    y0, slope = sp.simplify(expr.subs(x, x0)), sp.simplify(sp.diff(expr, x).subs(x, x0))
    tangent = sp.Eq(sp.Symbol("y"), sp.simplify(y0 + slope * (x - x0)))
    if slope == 0:
        normal = sp.Eq(x, x0)
    else:
        normal = sp.Eq(sp.Symbol("y"), sp.simplify(y0 - (x - x0) / slope))
    return {
        "point": {"x": str(x0), "y": str(y0)}, "slope": _render(slope),
        "tangent": _render(tangent), "normal": _render(normal),
        "visual": "tangent_secant",
    }


@tool
def calculus_definite_integral(
    expression: str, lower: str, upper: str, variable: str = "x"
) -> dict[str, Any]:
    """Evaluate a definite integral with antiderivative and average value."""
    x = sp.Symbol(variable, real=True)
    expr = _parse(expression, {variable: x})
    a, b = _parse(lower, {variable: x}), _parse(upper, {variable: x})
    antiderivative = sp.integrate(expr, x)
    value = sp.simplify(sp.integrate(expr, (x, a, b)))
    return {
        "integrand": expression, "bounds": [lower, upper],
        "antiderivative": _render(antiderivative), "value": _render(value),
        "average_value": _render(sp.simplify(value / (b - a))),
        "numeric_value": float(sp.N(value)),
        "visual": "riemann_area + integral_accumulation",
    }


@tool
def calculus_area_between_curves(
    upper_expression: str, lower_expression: str, lower: str, upper: str, variable: str = "x"
) -> dict[str, Any]:
    """Compute signed and geometric area between two curves over an interval."""
    x = sp.Symbol(variable, real=True)
    top = _parse(upper_expression, {variable: x})
    bottom = _parse(lower_expression, {variable: x})
    a, b = _parse(lower, {variable: x}), _parse(upper, {variable: x})
    difference = sp.simplify(top - bottom)
    crossings = [root for root in _real_solutions(difference, x) if bool(a <= root <= b)]
    signed = sp.simplify(sp.integrate(difference, (x, a, b)))
    boundaries = [a, *crossings, b]
    geometric = sp.S.Zero
    pieces = []
    for start, end in pairwise(boundaries):
        value = sp.simplify(sp.integrate(difference, (x, start, end)))
        geometric += abs(value)
        pieces.append({"from": str(start), "to": str(end), "signed_area": str(value)})
    return {
        "upper": upper_expression, "lower": lower_expression, "bounds": [lower, upper],
        "intersections_in_interval": [str(root) for root in crossings],
        "signed_area": _render(signed), "geometric_area": _render(sp.simplify(geometric)),
        "pieces": pieces, "visual": "area_between_curves",
    }


@tool
def calculus_taylor_approximation(
    expression: str, around: str, order: int, at: str = "", variable: str = "x"
) -> dict[str, Any]:
    """Compute a Taylor polynomial and, optionally, its exact approximation error."""
    if not 0 <= order <= 16:
        raise ToolError("order must be between 0 and 16")
    x = sp.Symbol(variable, real=True)
    expr, centre = _parse(expression, {variable: x}), _parse(around, {variable: x})
    polynomial = sp.series(expr, x, centre, order + 1).removeO()
    result: dict[str, Any] = {
        "expression": expression, "around": around, "order": order,
        "polynomial": _render(polynomial), "visual": "taylor_comparison",
    }
    if at:
        target = _parse(at, {variable: x})
        exact, approximation = sp.simplify(expr.subs(x, target)), sp.simplify(polynomial.subs(x, target))
        result["at"] = at
        result["exact"] = _render(exact)
        result["approximation"] = _render(approximation)
        result["error"] = _render(sp.simplify(exact - approximation))
    return result


@tool
def calculus_parametric_analysis(
    x_expression: str, y_expression: str, at: str, parameter: str = "t"
) -> dict[str, Any]:
    """Analyse velocity, tangent slope, and curvature of a parametric curve."""
    t = sp.Symbol(parameter, real=True)
    x, y, t0 = _parse(x_expression, {parameter: t}), _parse(y_expression, {parameter: t}), _parse(at, {parameter: t})
    dx, dy = sp.diff(x, t), sp.diff(y, t)
    speed = sp.simplify(sp.sqrt(dx**2 + dy**2))
    slope = sp.simplify(dy / dx) if dx != 0 else sp.oo
    curvature = sp.simplify(abs(dx * sp.diff(dy, t) - dy * sp.diff(dx, t)) / (dx**2 + dy**2) ** sp.Rational(3, 2))
    return {
        "parameter": parameter, "at": at,
        "point": {"x": str(sp.simplify(x.subs(t, t0))), "y": str(sp.simplify(y.subs(t, t0)))},
        "velocity": {"x": _render(dx), "y": _render(dy)},
        "speed": _render(speed), "slope": _render(slope), "curvature": _render(curvature),
        "visual": "parametric_curve",
    }


@tool
def calculus_multivariable_analysis(
    expression: str, variables: list[str] | None = None, at: list[str] | None = None
) -> dict[str, Any]:
    """Compute gradient, Hessian, and local second-derivative classification."""
    expr = _parse(expression)
    names = variables or sorted(str(symbol) for symbol in expr.free_symbols)
    if not 1 <= len(names) <= 3:
        raise ToolError("supply between one and three variables")
    # Keep symbol assumptions aligned with parse_expr.  A separately-created
    # Symbol("x", real=True) does not substitute into an assumption-free x.
    symbols = [sp.Symbol(name) for name in names]
    gradient = [sp.simplify(sp.diff(expr, symbol)) for symbol in symbols]
    hessian = sp.hessian(expr, symbols)
    result: dict[str, Any] = {
        "expression": expression, "variables": names,
        "gradient": [str(item) for item in gradient],
        "gradient_latex": [sp.latex(item) for item in gradient],
        "hessian": [[str(item) for item in row] for row in hessian.tolist()],
        "visual": "gradient_surface" if len(names) == 2 else "function_plot",
    }
    if at is not None:
        if len(at) != len(symbols):
            raise ToolError("at must have one coordinate per variable")
        point = [_parse(value) for value in at]
        substitution = dict(zip(symbols, point, strict=True))
        h_at = sp.Matrix(hessian.subs(substitution))
        result["at"] = at
        result["value"] = _render(sp.simplify(expr.subs(substitution)))
        result["gradient_at"] = [str(sp.simplify(item.subs(substitution))) for item in gradient]
        result["hessian_at"] = [[str(item) for item in row] for row in h_at.tolist()]
        if len(symbols) == 2:
            determinant = sp.simplify(h_at.det())
            f_xx = h_at[0, 0]
            classification = "saddle or inconclusive"
            if determinant.is_positive and f_xx.is_positive:
                classification = "local minimum"
            elif determinant.is_positive and f_xx.is_negative:
                classification = "local maximum"
            result["second_derivative_test"] = {"determinant": str(determinant), "classification": classification}
    return result


@tool
def calculus_autonomous_ode(rhs: str, variable: str = "y") -> dict[str, Any]:
    """Find equilibria and stability for y' = f(y), ready for a phase-line animation."""
    y = sp.Symbol(variable, real=True)
    field = _parse(rhs, {variable: y})
    derivative = sp.diff(field, y)
    equilibria = []
    for point in _real_solutions(field, y):
        test = sp.simplify(derivative.subs(y, point))
        stability = "inconclusive"
        if test.is_negative:
            stability = "stable"
        elif test.is_positive:
            stability = "unstable"
        equilibria.append({"value": str(point), "field_derivative": str(test), "stability": stability})
    return {
        "equation": f"{variable}' = {rhs}", "equilibria": equilibria,
        "field_derivative": _render(derivative), "visual": "phase_line + vector_field",
    }
