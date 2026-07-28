"""Exact Complex Numbers tools for algebra and Argand-plane geometry."""

from __future__ import annotations

from typing import Any, Literal

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


def _complex(expression: str) -> sp.Expr:
    try:
        return sp.simplify(sp.sympify(expression, locals={"i": sp.I, "I": sp.I}))
    except (TypeError, ValueError, sp.SympifyError) as error:
        raise ToolError(f"could not parse complex expression {expression!r}: {error}") from error


def _summary(value: sp.Expr) -> dict[str, Any]:
    real, imaginary = sp.simplify(sp.re(value)), sp.simplify(sp.im(value))
    modulus, argument = sp.simplify(sp.Abs(value)), sp.simplify(sp.arg(value))
    return {
        "result": str(value), "real": str(real), "imaginary": str(imaginary),
        "conjugate": str(sp.conjugate(value)), "modulus": str(modulus), "argument": str(argument),
        "polar_latex": rf"{sp.latex(modulus)}\left(\cos\left({sp.latex(argument)}\right)+i\sin\left({sp.latex(argument)}\right)\right)",
        "argand_point": [str(real), str(imaginary)],
    }


@tool
def complex_number_analysis(expression: str) -> dict[str, Any]:
    """Compute real/imaginary parts, conjugate, modulus, argument, and polar form.

    Args:
        expression: Complex expression using I or i, e.g. "3+4*I".
    """
    return {"input": expression, **_summary(_complex(expression))}


@tool
def complex_number_operation(
    left: str, right: str, operation: Literal["add", "subtract", "multiply", "divide", "power"]
) -> dict[str, Any]:
    """Perform and analyse an exact operation on two complex numbers.

    Args:
        left: First complex expression.
        right: Second complex expression; exponent for power.
        operation: add, subtract, multiply, divide, or power.
    """
    first, second = _complex(left), _complex(right)
    if operation == "divide" and second == 0:
        raise ToolError("division by zero complex number is undefined")
    if operation == "add":
        result = first + second
    elif operation == "subtract":
        result = first - second
    elif operation == "multiply":
        result = first * second
    elif operation == "divide":
        result = first / second
    else:
        result = first**second
    return {"operation": operation, "left": left, "right": right, **_summary(sp.simplify(result))}


@tool
def complex_polynomial_roots(expression: str, variable: str = "z") -> dict[str, Any]:
    """Solve a polynomial over the complex numbers and return Argand-plane roots.

    Args:
        expression: Polynomial equation or expression, e.g. "z**4-1=0".
        variable: Complex variable name.
    """
    name = sp.Symbol(variable)
    try:
        left, separator, right = expression.partition("=")
        polynomial = sp.sympify(left, locals={variable: name, "i": sp.I, "I": sp.I}) - (sp.sympify(right, locals={variable: name, "i": sp.I, "I": sp.I}) if separator else 0)
    except (TypeError, ValueError, sp.SympifyError) as error:
        raise ToolError(f"could not parse polynomial {expression!r}: {error}") from error
    roots = sp.solve(polynomial, name)
    return {"equation": str(sp.factor(polynomial)), "roots": [_summary(sp.simplify(root)) for root in roots], "count": len(roots)}


@tool
def roots_of_unity(order: int) -> dict[str, Any]:
    """Compute nth roots of unity with exact angles and Argand-plane coordinates.

    Args:
        order: Positive integer n in z^n=1, from 1 to 30.
    """
    if not 1 <= order <= 30:
        raise ToolError("order must be between 1 and 30")
    roots = [sp.exp(2 * sp.pi * sp.I * index / order) for index in range(order)]
    return {
        "equation_latex": rf"z^{order}=1",
        "roots": [{"index": index, "angle": str(sp.simplify(2 * sp.pi * index / order)), "point": [str(sp.simplify(sp.re(root))), str(sp.simplify(sp.im(root)))]} for index, root in enumerate(roots)],
        "geometry": f"regular {order}-gon on the unit circle",
        "visual": "roots_of_unity_polygon",
    }


@tool
def complex_locus(condition: Literal["modulus", "argument", "equidistant"], value: str, second_value: str = "") -> dict[str, Any]:
    """Translate standard complex-number loci into an Argand-plane description.

    Args:
        condition: modulus for |z|=r, argument for arg(z)=theta, or equidistant for |z-a|=|z-b|.
        value: Radius/exact angle/first fixed complex number respectively.
        second_value: Second fixed complex number for equidistant only.
    """
    if condition == "modulus":
        radius = _complex(value)
        if sp.im(radius) != 0 or radius < 0:
            raise ToolError("a modulus radius must be a non-negative real value")
        return {"condition": "|z|=r", "radius": str(radius), "locus": "circle centred at the origin", "visual": "complex_plane_vector"}
    if condition == "argument":
        angle = _complex(value)
        if sp.im(angle) != 0:
            raise ToolError("an argument must be real")
        return {"condition": "arg(z)=theta", "angle": str(angle), "locus": "ray from the origin, excluding the origin", "visual": "complex_plane_vector"}
    if not second_value:
        raise ToolError("equidistant locus needs two fixed complex numbers")
    first, second = _complex(value), _complex(second_value)
    if first == second:
        raise ToolError("the two fixed points must be distinct")
    midpoint = sp.simplify((first + second) / 2)
    return {"condition": "|z-a|=|z-b|", "a": str(first), "b": str(second), "midpoint": _summary(midpoint)["argand_point"], "locus": "perpendicular bisector of the segment joining a and b", "visual": "complex_plane_vector"}
