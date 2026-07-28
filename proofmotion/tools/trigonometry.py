"""Exact trigonometry workflows for solving and teaching."""

from __future__ import annotations

from typing import Any, Literal

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


def _parse(value: str, local: dict[str, Any] | None = None) -> sp.Expr:
    from sympy.parsing.sympy_parser import implicit_multiplication_application, parse_expr, standard_transformations
    try:
        return parse_expr(value, local_dict=local or {}, transformations=(*standard_transformations, implicit_multiplication_application))
    except (SyntaxError, TypeError, ValueError, AttributeError) as error:
        raise ToolError(f"could not parse {value!r}: {error}") from error


def _render(value: Any) -> dict[str, str]:
    return {"result": str(sp.simplify(value)), "latex": sp.latex(sp.simplify(value))}


@tool
def trig_exact_values(angle_degrees: str) -> dict[str, Any]:
    """Return exact sine, cosine, tangent, secant, cosecant, and cotangent of an angle in degrees."""
    degrees = _parse(angle_degrees)
    theta = sp.pi * degrees / 180
    sine, cosine = sp.simplify(sp.sin(theta)), sp.simplify(sp.cos(theta))
    return {
        "angle_degrees": str(degrees), "angle_radians": _render(theta),
        "sin": _render(sine), "cos": _render(cosine),
        "tan": _render(sp.simplify(sine / cosine)) if cosine != 0 else {"result": "undefined", "latex": r"\text{undefined}"},
        "sec": _render(sp.simplify(1 / cosine)) if cosine != 0 else {"result": "undefined", "latex": r"\text{undefined}"},
        "csc": _render(sp.simplify(1 / sine)) if sine != 0 else {"result": "undefined", "latex": r"\text{undefined}"},
        "cot": _render(sp.simplify(cosine / sine)) if sine != 0 else {"result": "undefined", "latex": r"\text{undefined}"},
        "visual": "unit_circle",
    }


@tool
def trig_identity_check(left: str, right: str, variable: str = "x") -> dict[str, Any]:
    """Verify a trigonometric identity symbolically and report the simplified difference."""
    x = sp.Symbol(variable, real=True)
    difference = sp.trigsimp(_parse(left, {variable: x}) - _parse(right, {variable: x}))
    return {"left": left, "right": right, "difference": _render(difference), "valid": bool(difference == 0), "visual": "unit_circle"}


@tool
def trig_equation_solve(equation: str, variable: str = "x", lower_degrees: float = 0, upper_degrees: float = 360) -> dict[str, Any]:
    """Solve a trigonometric equation on a closed degree interval, returning every solution."""
    x = sp.Symbol(variable, real=True)
    left, separator, right = equation.partition("=")
    expression = _parse(left, {variable: x}) - (_parse(right, {variable: x}) if separator else 0)
    interval = sp.Interval(sp.pi * lower_degrees / 180, sp.pi * upper_degrees / 180)
    try:
        found = sp.solveset(expression, x, domain=interval)
    except (NotImplementedError, ValueError, TypeError) as error:
        raise ToolError(f"could not solve the trigonometric equation: {error}") from error
    if not isinstance(found, sp.FiniteSet):
        raise ToolError("solution set is not finite on this interval; use a narrower interval")
    values = sorted(found, key=lambda value: float(sp.N(value)))
    return {
        "equation": equation, "interval_degrees": [lower_degrees, upper_degrees],
        "solutions_radians": [str(value) for value in values],
        "solutions_degrees": [str(sp.simplify(180 * value / sp.pi)) for value in values],
        "verified": [bool(sp.simplify(expression.subs(x, value)) == 0) for value in values],
        "visual": "trig_wave",
    }


@tool
def trig_inverse_principal(function: Literal["asin", "acos", "atan"], value: str) -> dict[str, Any]:
    """Evaluate an inverse trig function with its principal range made explicit."""
    argument = _parse(value)
    operation = {"asin": sp.asin, "acos": sp.acos, "atan": sp.atan}[function]
    if function in {"asin", "acos"} and not argument.is_real:
        raise ToolError("inverse sine and cosine require a real input in [-1, 1]")
    result = sp.simplify(operation(argument))
    ranges = {"asin": r"[-\pi/2,\pi/2]", "acos": r"[0,\pi]", "atan": r"(-\pi/2,\pi/2)"}
    return {"function": function, "input": value, "principal_value": _render(result), "principal_range": ranges[function], "degrees": _render(sp.simplify(180 * result / sp.pi)), "visual": "unit_circle"}


@tool
def trig_law_of_cosines(side_a: str, side_b: str, included_angle_degrees: str) -> dict[str, Any]:
    """Find the third side from two sides and their included angle using the cosine rule."""
    a, b, degrees = _parse(side_a), _parse(side_b), _parse(included_angle_degrees)
    if a <= 0 or b <= 0:
        raise ToolError("side lengths must be positive")
    angle = sp.pi * degrees / 180
    third = sp.simplify(sp.sqrt(a**2 + b**2 - 2 * a * b * sp.cos(angle)))
    return {"sides": [str(a), str(b)], "included_angle_degrees": str(degrees), "third_side": _render(third), "equation": _render(third**2 - (a**2 + b**2 - 2*a*b*sp.cos(angle))), "visual": "trig_triangle"}


@tool
def trig_law_of_sines(known_side: str, known_angle_degrees: str, target_angle_degrees: str) -> dict[str, Any]:
    """Find a side using a/sin(A)=b/sin(B), while flagging the ambiguous SSA case."""
    a, first, second = _parse(known_side), _parse(known_angle_degrees), _parse(target_angle_degrees)
    if a <= 0 or not (0 < first < 180 and 0 < second < 180):
        raise ToolError("side must be positive and angles must lie between 0 and 180 degrees")
    target = sp.simplify(a * sp.sin(sp.pi * second / 180) / sp.sin(sp.pi * first / 180))
    return {"known_side": str(a), "known_angle_degrees": str(first), "target_angle_degrees": str(second), "target_side": _render(target), "remaining_angle_degrees": _render(180 - first - second), "visual": "trig_triangle"}


@tool
def trig_wave_analysis(expression: str, variable: str = "x") -> dict[str, Any]:
    """Extract amplitude, period, phase shift, and vertical shift for A sin(B(x-C))+D or cosine form."""
    x = sp.Symbol(variable, real=True)
    # Keep sin(B(x-C)) intact.  expand_trig turns it into several atoms and
    # makes a simple transformed wave look like a sum of unrelated waves.
    expr = _parse(expression, {variable: x})
    functions = list(expr.atoms(sp.sin, sp.cos))
    if len(functions) != 1:
        raise ToolError("supply a single sine or cosine wave in a factored form")
    wave = functions[0]
    argument = wave.args[0]
    coefficient = sp.simplify(sp.diff(argument, x))
    if coefficient == 0:
        raise ToolError("the wave must depend on the supplied variable")
    # Evaluate coefficients by treating the trig atom as one algebraic symbol.
    atom = sp.Symbol("wave")
    replaced = expr.xreplace({wave: atom})
    amplitude = sp.simplify(replaced.coeff(atom))
    vertical = sp.simplify(replaced.subs(atom, 0))
    phase = sp.simplify(-argument.subs(x, 0) / coefficient)
    return {"expression": expression, "kind": "sine" if wave.func == sp.sin else "cosine", "amplitude": _render(abs(amplitude)), "signed_amplitude": _render(amplitude), "period": _render(2 * sp.pi / abs(coefficient)), "phase_shift": _render(phase), "vertical_shift": _render(vertical), "visual": "trig_wave"}
