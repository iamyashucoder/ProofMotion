"""Exact workflows for the Coordinate Geometry chapter.

These build on :mod:`geometry` rather than replace it.  They return the linked
facts a student needs to solve and draw a coordinate-geometry problem without
reading values from a sketch.
"""

from __future__ import annotations

from typing import Any, Literal

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


def _expression(equation: str, local: dict[str, Any]) -> sp.Expr:
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    try:
        left, separator, right = equation.partition("=")
        return sp.expand(parse_expr(left, local_dict=local, transformations=(*standard_transformations, implicit_multiplication_application)) - (parse_expr(right, local_dict=local, transformations=(*standard_transformations, implicit_multiplication_application)) if separator else 0))
    except (SyntaxError, TypeError, ValueError, AttributeError) as error:
        raise ToolError(f"could not parse {equation!r}: {error}") from error


def _point(value: list) -> tuple[sp.Expr, sp.Expr]:
    if len(value) != 2:
        raise ToolError("each point must have [x, y]")
    return sp.nsimplify(value[0]), sp.nsimplify(value[1])


def _render(value: Any) -> dict[str, str]:
    return {"result": str(sp.simplify(value)), "latex": sp.latex(sp.simplify(value))}


@tool
def coordinate_line_analysis(first_line: str, second_line: str = "") -> dict[str, Any]:
    """Analyse one or two Cartesian lines: coefficients, slope, angle and intersection."""
    x, y = sp.symbols("x y", real=True)
    first = _expression(first_line, {"x": x, "y": y})
    a1, b1, c1 = (sp.expand(first).coeff(symbol) for symbol in (x, y, sp.S.One))
    # coeff(1) is not the constant term. Substitute origin instead.
    c1 = sp.simplify(first.subs({x: 0, y: 0}))
    if a1 == 0 and b1 == 0:
        raise ToolError("a line must contain x or y")
    result: dict[str, Any] = {
        "first_line": {"equation": _render(first), "coefficients": [str(a1), str(b1), str(c1)], "slope": str(sp.oo if b1 == 0 else sp.simplify(-a1 / b1)), "x_intercept": str(sp.nan if a1 == 0 else sp.simplify(-c1 / a1)), "y_intercept": str(sp.nan if b1 == 0 else sp.simplify(-c1 / b1))},
        "visual": "coordinate_line_pair",
    }
    if second_line:
        second = _expression(second_line, {"x": x, "y": y})
        a2, b2 = sp.expand(second).coeff(x), sp.expand(second).coeff(y)
        c2 = sp.simplify(second.subs({x: 0, y: 0}))
        determinant = sp.simplify(a1 * b2 - a2 * b1)
        intersection = sp.solve([first, second], [x, y], dict=True) if determinant != 0 else []
        dot = sp.simplify(a1 * a2 + b1 * b2)
        result["second_line"] = {"equation": _render(second), "coefficients": [str(a2), str(b2), str(c2)]}
        result["relation"] = "intersecting" if determinant != 0 else ("coincident" if sp.simplify(a1 * c2 - a2 * c1) == 0 else "parallel")
        result["intersection"] = {key.name: str(value) for key, value in intersection[0].items()} if intersection else None
        result["perpendicular"] = bool(dot == 0)
        result["angle_tan"] = str(sp.Abs(determinant / dot)) if dot != 0 else "infinity"
    return result


@tool
def coordinate_circle_analysis(equation: str, point: list | None = None) -> dict[str, Any]:
    """Extract centre, radius, and optional tangent/normal from a circle equation."""
    x, y = sp.symbols("x y", real=True)
    expr = _expression(equation, {"x": x, "y": y})
    ax2, ay2 = expr.coeff(x, 2), expr.coeff(y, 2)
    if ax2 == 0 or sp.simplify(ax2 - ay2) != 0 or expr.coeff(x * y) != 0:
        raise ToolError("expected a circle equation with equal x^2 and y^2 coefficients and no xy term")
    scale = ax2
    linear_x, linear_y = expr.coeff(x) / scale, expr.coeff(y) / scale
    constant = expr.subs({x: 0, y: 0}) / scale
    h, k = sp.simplify(-linear_x / 2), sp.simplify(-linear_y / 2)
    radius_squared = sp.simplify(h**2 + k**2 - constant)
    if radius_squared <= 0:
        raise ToolError("the equation does not describe a non-degenerate real circle")
    result: dict[str, Any] = {
        "equation": equation, "centre": [str(h), str(k)], "radius": _render(sp.sqrt(radius_squared)),
        "standard_form": _render((x - h) ** 2 + (y - k) ** 2 - radius_squared),
        "visual": "circle_coordinate_diagram",
    }
    if point is not None:
        px, py = _point(point)
        on_circle = sp.simplify((px - h) ** 2 + (py - k) ** 2 - radius_squared) == 0
        result["point_on_circle"] = on_circle
        if on_circle:
            normal = sp.Eq((py - k) * (x - px) - (px - h) * (y - py), 0)
            tangent = sp.Eq((px - h) * (x - px) + (py - k) * (y - py), 0)
            result["normal"] = _render(normal)
            result["tangent"] = _render(tangent)
    return result


@tool
def coordinate_conic_classify(equation: str) -> dict[str, Any]:
    """Classify a general second-degree equation by its discriminant and centre."""
    x, y = sp.symbols("x y", real=True)
    expr = _expression(equation, {"x": x, "y": y})
    a, b, c = expr.coeff(x, 2), expr.coeff(x * y), expr.coeff(y, 2)
    discriminant = sp.simplify(b**2 - 4 * a * c)
    if a == b == c == 0:
        raise ToolError("expected a second-degree equation")
    kind = "parabola" if discriminant == 0 else ("ellipse or circle" if discriminant.is_negative else "hyperbola")
    centre_solution = sp.solve([sp.diff(expr, x), sp.diff(expr, y)], [x, y], dict=True)
    return {
        "equation": equation, "quadratic_coefficients": {"A": str(a), "B": str(b), "C": str(c)},
        "discriminant_B2_minus_4AC": _render(discriminant), "classification": kind,
        "centre": ({key.name: str(value) for key, value in centre_solution[0].items()} if centre_solution else None),
        "visual": "conic_coordinate_diagram",
    }


@tool
def coordinate_triangle_centres(points: list) -> dict[str, Any]:
    """Compute centroid, circumcentre, orthocentre, incenter, and area of a coordinate triangle."""
    if len(points) != 3:
        raise ToolError("exactly three points are required")
    from sympy import geometry as geo

    vertices = [geo.Point2D(*_point(point)) for point in points]
    triangle = geo.Triangle(*vertices)
    if triangle.area == 0:
        raise ToolError("the vertices are collinear")
    def pair(item: geo.Point2D) -> list[str]:
        return [str(item.x), str(item.y)]
    return {
        "vertices": points, "area": _render(abs(triangle.area)),
        "centroid": pair(triangle.centroid), "circumcentre": pair(triangle.circumcircle.center),
        "orthocentre": pair(triangle.orthocenter), "incenter": pair(triangle.incenter),
        "visual": "coordinate_triangle_centres",
    }


@tool
def coordinate_section_formula(first: list, second: list, m: str, n: str, mode: Literal["internal", "external"] = "internal") -> dict[str, Any]:
    """Divide a segment in a specified internal or external ratio m:n."""
    x1, y1 = _point(first)
    x2, y2 = _point(second)
    left, right = sp.nsimplify(m), sp.nsimplify(n)
    if left <= 0 or right <= 0 or (mode == "external" and left == right):
        raise ToolError("ratios must be positive; external division needs unequal ratios")
    sign = 1 if mode == "internal" else -1
    denominator = left + sign * right
    point = (sp.simplify((left * x2 + sign * right * x1) / denominator), sp.simplify((left * y2 + sign * right * y1) / denominator))
    return {"mode": mode, "ratio": f"{m}:{n}", "point": [str(point[0]), str(point[1])], "visual": "coordinate_line_pair"}


@tool
def coordinate_transform(points: list, operation: Literal["translate", "rotate", "reflect_x", "reflect_y", "reflect_origin"], values: list | None = None) -> dict[str, Any]:
    """Apply an exact translation, rotation, or reflection to coordinate points."""
    source = [_point(point) for point in points]
    if not source:
        raise ToolError("at least one point is required")
    if operation == "translate":
        if not values or len(values) != 2:
            raise ToolError("translation needs [dx, dy]")
        dx, dy = map(sp.nsimplify, values)
        transformed = [(x + dx, y + dy) for x, y in source]
    elif operation == "rotate":
        if not values or len(values) not in {1, 3}:
            raise ToolError("rotation needs [angle_degrees] or [angle_degrees, cx, cy]")
        angle = sp.pi * sp.nsimplify(values[0]) / 180
        cx, cy = (sp.S.Zero, sp.S.Zero) if len(values) == 1 else map(sp.nsimplify, values[1:])
        transformed = [(sp.simplify(cx + (x - cx) * sp.cos(angle) - (y - cy) * sp.sin(angle)), sp.simplify(cy + (x - cx) * sp.sin(angle) + (y - cy) * sp.cos(angle))) for x, y in source]
    else:
        transformed = [({"reflect_x": (x, -y), "reflect_y": (-x, y), "reflect_origin": (-x, -y)}[operation]) for x, y in source]
    return {"operation": operation, "original": [[str(x), str(y)] for x, y in source], "transformed": [[str(x), str(y)] for x, y in transformed], "visual": "coordinate_transformation"}


@tool
def coordinate_locus_ratio(first_focus: list, second_focus: list, ratio: str) -> dict[str, Any]:
    """Derive the locus PF1/PF2 = k, classifying the Apollonius circle or line."""
    x, y = sp.symbols("x y", real=True)
    x1, y1 = _point(first_focus)
    x2, y2 = _point(second_focus)
    k = sp.nsimplify(ratio)
    if k <= 0:
        raise ToolError("the distance ratio must be positive")
    equation = sp.expand((x - x1) ** 2 + (y - y1) ** 2 - k**2 * ((x - x2) ** 2 + (y - y2) ** 2))
    return {"ratio": str(k), "equation": _render(equation), "classification": "perpendicular bisector line" if k == 1 else "Apollonius circle", "visual": "conic_coordinate_diagram"}


@tool
def hyperbola_latus_rectum_right_angle(focus_distance: str) -> dict[str, Any]:
    """Solve the standard hyperbola latus-rectum right-angle configuration exactly.

    For x²/a² - y²/b² = 1 with foci (±c, 0), the latus rectum through (c, 0)
    subtends a right angle at (-c, 0).  This derives a, b, a²b², and the
    coefficients in a²b² = alpha*sqrt(2) - beta.
    """
    c = sp.nsimplify(focus_distance)
    if c <= 0:
        raise ToolError("focus_distance c must be positive")
    a = sp.simplify(c * (sp.sqrt(2) - 1))
    a_squared = sp.simplify(a**2)
    b_squared = sp.simplify(2 * c * a)
    product = sp.collect(sp.expand(a_squared * b_squared), sp.sqrt(2))
    alpha = sp.simplify(product.coeff(sp.sqrt(2)))
    beta = sp.simplify(-product.subs(sp.sqrt(2), 0))
    return {
        "focus_distance": str(c),
        "focus_relation": _render(sp.Eq(sp.Symbol("c") ** 2, sp.Symbol("a") ** 2 + sp.Symbol("b") ** 2)),
        "right_angle_condition": _render(sp.Eq(sp.Symbol("b") ** 2, 2 * sp.Symbol("c") * sp.Symbol("a"))),
        "a": _render(a), "a_squared": _render(a_squared), "b_squared": _render(b_squared),
        "a_squared_b_squared": _render(product),
        "alpha": str(alpha), "beta": str(beta), "alpha_plus_beta": str(sp.simplify(alpha + beta)),
        "verification": {
            "a_squared_plus_b_squared": _render(sp.simplify(a_squared + b_squared)),
            "equals_c_squared": bool(sp.simplify(a_squared + b_squared - c**2) == 0),
        },
        "visual": "conic_coordinate_diagram + coordinate_line_pair",
    }
