"""Exact coordinate-geometry tools for lines and planes in three dimensions."""

from __future__ import annotations

from typing import Any

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


def _vector(values: list, name: str) -> sp.Matrix:
    if len(values) != 3:
        raise ToolError(f"{name} must contain exactly three coordinates")
    try:
        return sp.Matrix([sp.sympify(value) for value in values])
    except (TypeError, ValueError, sp.SympifyError) as error:
        raise ToolError(f"could not parse {name}: {error}") from error


def _plane(values: list) -> tuple[sp.Matrix, sp.Expr]:
    if len(values) != 4:
        raise ToolError("plane must be [a, b, c, d] for ax+by+cz=d")
    normal, offset = _vector(values[:3], "plane normal"), sp.sympify(values[3])
    if normal.dot(normal) == 0:
        raise ToolError("plane normal cannot be the zero vector")
    return normal, offset


def _list(vector: sp.Matrix) -> list[str]:
    return [str(sp.simplify(value)) for value in vector]


@tool
def three_d_line_plane_intersection(point: list, direction: list, plane: list) -> dict[str, Any]:
    """Classify a 3D line against a plane and compute the intersection if it exists.

    Args:
        point: A point on the line [x, y, z].
        direction: Direction vector of the line [l, m, n].
        plane: Plane coefficients [a, b, c, d] for ax+by+cz=d.
    """
    base, vector = _vector(point, "point"), _vector(direction, "direction")
    normal, offset = _plane(plane)
    dot = sp.simplify(normal.dot(vector))
    residual = sp.simplify(normal.dot(base) - offset)
    if dot == 0:
        relation = "line_in_plane" if residual == 0 else "parallel_no_intersection"
        return {"relation": relation, "normal_dot_direction": str(dot), "intersection": None}
    parameter = sp.simplify(-residual / dot)
    intersection = sp.simplify(base + parameter * vector)
    return {"relation": "intersects", "parameter": str(parameter), "intersection": _list(intersection), "normal_dot_direction": str(dot)}


@tool
def three_d_line_relation(point1: list, direction1: list, point2: list, direction2: list) -> dict[str, Any]:
    """Find angle, intersection, and shortest distance between two 3D lines.

    Args:
        point1: Point on first line.
        direction1: Direction of first line.
        point2: Point on second line.
        direction2: Direction of second line.
    """
    p1, d1, p2, d2 = _vector(point1, "point1"), _vector(direction1, "direction1"), _vector(point2, "point2"), _vector(direction2, "direction2")
    if d1.dot(d1) == 0 or d2.dot(d2) == 0:
        raise ToolError("line directions cannot be zero")
    cross, difference = d1.cross(d2), p2 - p1
    cosine = sp.simplify(abs(d1.dot(d2)) / sp.sqrt(d1.dot(d1) * d2.dot(d2)))
    if cross.dot(cross) == 0:
        distance = sp.simplify(difference.cross(d1).norm() / sp.sqrt(d1.dot(d1)))
        return {"relation": "coincident" if distance == 0 else "parallel", "angle_cosine": str(cosine), "shortest_distance": str(distance), "intersection": None}
    distance = sp.simplify(abs(difference.dot(cross)) / sp.sqrt(cross.dot(cross)))
    t, u = sp.symbols("t u")
    solution = sp.solve(list(p1 + t * d1 - p2 - u * d2), (t, u), dict=True)
    if solution:
        intersection = sp.simplify(p1 + solution[0][t] * d1)
        return {"relation": "intersecting", "angle_cosine": str(cosine), "shortest_distance": "0", "intersection": _list(intersection)}
    return {"relation": "skew", "angle_cosine": str(cosine), "shortest_distance": str(distance), "intersection": None, "common_perpendicular_direction": _list(cross)}


@tool
def three_d_plane_relation(plane1: list, plane2: list) -> dict[str, Any]:
    """Classify two planes and calculate their angle or separation.

    Args:
        plane1: First [a, b, c, d] plane.
        plane2: Second [a, b, c, d] plane.
    """
    n1, d1 = _plane(plane1)
    n2, d2 = _plane(plane2)
    cross = n1.cross(n2)
    cosine = sp.simplify(abs(n1.dot(n2)) / sp.sqrt(n1.dot(n1) * n2.dot(n2)))
    if cross.dot(cross) == 0:
        probe = next((index for index, value in enumerate(n1) if value != 0), 0)
        scale = sp.simplify(n2[probe] / n1[probe])
        same = sp.simplify(d2 - scale * d1) == 0
        distance = sp.Integer(0) if same else sp.simplify(abs(d2 - scale * d1) / sp.sqrt(n2.dot(n2)))
        return {"relation": "coincident" if same else "parallel", "angle_cosine": "1", "distance": str(distance), "intersection_direction": None}
    return {"relation": "intersecting", "angle_cosine": str(cosine), "distance": "0", "intersection_direction": _list(cross)}


@tool
def three_d_point_distance(point: list, plane: list | None = None, line_point: list | None = None, line_direction: list | None = None) -> dict[str, Any]:
    """Compute exact distance from a 3D point to one plane or one line.

    Args:
        point: Point [x, y, z].
        plane: Optional plane [a, b, c, d].
        line_point: Optional point on a line.
        line_direction: Optional line direction.
    """
    target = _vector(point, "point")
    if plane is not None and line_point is None and line_direction is None:
        normal, offset = _plane(plane)
        distance = sp.simplify(abs(normal.dot(target) - offset) / sp.sqrt(normal.dot(normal)))
        foot = sp.simplify(target - (normal.dot(target) - offset) / normal.dot(normal) * normal)
        return {"object": "plane", "distance": str(distance), "foot": _list(foot)}
    if plane is None and line_point is not None and line_direction is not None:
        base, direction = _vector(line_point, "line_point"), _vector(line_direction, "line_direction")
        if direction.dot(direction) == 0:
            raise ToolError("line_direction cannot be zero")
        parameter = sp.simplify(direction.dot(target - base) / direction.dot(direction))
        foot = sp.simplify(base + parameter * direction)
        return {"object": "line", "distance": str(sp.simplify((target - foot).norm())), "foot": _list(foot), "parameter": str(parameter)}
    raise ToolError("give either plane, or both line_point and line_direction")


@tool
def three_d_plane_from_points(points: list) -> dict[str, Any]:
    """Build a plane equation from three non-collinear 3D points.

    Args:
        points: Exactly three points [[x1,y1,z1], [x2,y2,z2], [x3,y3,z3]].
    """
    if len(points) != 3:
        raise ToolError("three_d_plane_from_points needs exactly three points")
    first, second, third = (_vector(point, "point") for point in points)
    normal = (second - first).cross(third - first)
    if normal.dot(normal) == 0:
        raise ToolError("the three points are collinear and do not determine a plane")
    offset = sp.simplify(normal.dot(first))
    return {"normal": _list(normal), "plane": [*_list(normal), str(offset)], "equation_latex": rf"{sp.latex(normal[0])}x+{sp.latex(normal[1])}y+{sp.latex(normal[2])}z={sp.latex(offset)}"}
