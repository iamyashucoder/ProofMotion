"""Analytic geometry: exact intersections, distances, angles, and areas.

Geometry answers are the ones most often asserted from a sketch. These are
computed, so a claimed intersection point is one that actually lies on both
objects.
"""

from __future__ import annotations

from typing import Any, Literal

import sympy as sp
from sympy import geometry as geo

from proofmotion.runtime.registry import ToolError, tool


def _point(value: Any) -> geo.Point2D:
    try:
        x, y = value
        return geo.Point2D(sp.nsimplify(x), sp.nsimplify(y))
    except (TypeError, ValueError) as error:
        raise ToolError(f"expected a point as [x, y], got {value!r}") from error


@tool
def geometry_solve(
    operation: Literal[
        "distance", "midpoint", "line_through", "intersection", "angle",
        "triangle_properties", "circle_through", "collinear", "point_on_line",
    ],
    points: list | None = None,
    circle: list | None = None,
) -> dict[str, Any]:
    """Exact analytic geometry over points and circles.

    Args:
        operation: What to compute.
        points: Points as [[x, y], ...]. Two for distance or midpoint, three for
            angle or triangle_properties, four for the intersection of two lines.
        circle: A circle as [centre_x, centre_y, radius], for circle operations.
    """
    pts = [_point(p) for p in (points or [])]

    def need(count: int) -> None:
        if len(pts) < count:
            raise ToolError(f"{operation} needs {count} points, got {len(pts)}")

    try:
        if operation == "distance":
            need(2)
            value = pts[0].distance(pts[1])
            return {"operation": operation, "result": str(sp.simplify(value)), "decimal": float(value)}

        if operation == "midpoint":
            need(2)
            mid = pts[0].midpoint(pts[1])
            return {"operation": operation, "result": [str(mid.x), str(mid.y)]}

        if operation == "line_through":
            need(2)
            line = geo.Line(pts[0], pts[1])
            return {
                "operation": operation,
                "equation": str(line.equation()),
                "slope": str(line.slope),
                "latex": sp.latex(line.equation()),
            }

        if operation == "intersection":
            need(4)
            first, second = geo.Line(pts[0], pts[1]), geo.Line(pts[2], pts[3])
            meeting = first.intersection(second)
            if not meeting:
                return {"operation": operation, "result": None, "note": "the lines are parallel"}
            if isinstance(meeting[0], geo.Line):
                return {"operation": operation, "result": None, "note": "the lines are identical"}
            point = meeting[0]
            return {"operation": operation, "result": [str(point.x), str(point.y)],
                    "decimal": [float(point.x), float(point.y)]}

        if operation == "angle":
            need(3)
            angle = geo.Line(pts[1], pts[0]).angle_between(geo.Line(pts[1], pts[2]))
            return {
                "operation": operation, "vertex": str(pts[1]),
                "radians": str(sp.simplify(angle)), "degrees": round(float(sp.deg(angle)), 8),
            }

        if operation == "triangle_properties":
            need(3)
            # Check first: sympy hands back a Segment2D for collinear points, so
            # asking the "triangle" for its area raises AttributeError instead of
            # reaching a degenerate-area guard placed after construction.
            if geo.Point.is_collinear(*pts[:3]):
                raise ToolError("the three points are collinear, so they form no triangle")
            triangle = geo.Triangle(*pts[:3])
            angles = [round(float(sp.deg(a)), 6) for a in triangle.angles.values()]
            return {
                "operation": operation,
                "area": str(sp.simplify(abs(triangle.area))),
                "perimeter": str(sp.simplify(triangle.perimeter)),
                "sides": [str(sp.simplify(s.length)) for s in triangle.sides],
                "angles_degrees": angles,
                "angle_sum": round(sum(angles), 6),
                "is_right": bool(triangle.is_right()),
                "is_equilateral": bool(triangle.is_equilateral()),
            }

        if operation == "circle_through":
            need(3)
            circle_obj = geo.Circle(*pts[:3])
            return {
                "operation": operation,
                "centre": [str(circle_obj.center.x), str(circle_obj.center.y)],
                "radius": str(sp.simplify(circle_obj.radius)),
                "equation": str(circle_obj.equation()),
            }

        if operation == "collinear":
            need(3)
            return {"operation": operation, "collinear": bool(geo.Point.is_collinear(*pts))}

        need(3)
        line = geo.Line(pts[0], pts[1])
        return {"operation": operation, "on_line": bool(line.contains(pts[2])),
                "distance": float(line.distance(pts[2]))}

    except ToolError:
        raise
    except (ValueError, TypeError, ZeroDivisionError, NotImplementedError) as error:
        raise ToolError(f"{operation} failed: {error}") from error


@tool
def conic_properties(
    kind: Literal["circle", "ellipse", "parabola", "hyperbola"],
    parameters: list,
) -> dict[str, Any]:
    """Foci, eccentricity, axes and directrix for a conic in standard position.

    Args:
        kind: Which conic.
        parameters: circle [radius]; ellipse [a, b]; parabola [focal_length];
            hyperbola [a, b].
    """
    values = [float(v) for v in parameters]
    try:
        if kind == "circle":
            (radius,) = values
            return {"kind": kind, "radius": radius, "eccentricity": 0.0,
                    "area": round(sp.pi.evalf() * radius**2, 8), "foci": [[0.0, 0.0]]}
        if kind == "ellipse":
            a, b = values
            major, minor = max(a, b), min(a, b)
            c = float(sp.sqrt(major**2 - minor**2))
            focus = [[c, 0.0], [-c, 0.0]] if a >= b else [[0.0, c], [0.0, -c]]
            return {"kind": kind, "semi_major": major, "semi_minor": minor,
                    "eccentricity": round(c / major, 8), "foci": focus,
                    "area": round(float(sp.pi) * a * b, 8)}
        if kind == "parabola":
            (focal,) = values
            return {"kind": kind, "focal_length": focal, "eccentricity": 1.0,
                    "focus": [0.0, focal], "directrix": f"y = {-focal}"}
        a, b = values
        c = float(sp.sqrt(a**2 + b**2))
        return {"kind": kind, "a": a, "b": b, "eccentricity": round(c / a, 8),
                "foci": [[c, 0.0], [-c, 0.0]], "asymptotes": [f"y = {b / a:.6g}x", f"y = {-b / a:.6g}x"]}
    except (ValueError, TypeError, ZeroDivisionError) as error:
        raise ToolError(f"{kind} needs different parameters: {error}") from error
