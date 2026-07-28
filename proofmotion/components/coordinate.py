"""Coordinate-plane builders backed by exact coordinate inputs."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.regions import layout, place
from proofmotion.runtime.registry import ToolError


def _plane(extent: float):
    from manim import NumberPlane
    return NumberPlane(
        x_range=[-extent, extent, 1], y_range=[-extent, extent, 1],
        x_length=8.4, y_length=5.2,
        background_line_style={"stroke_color": "#334155", "stroke_width": 1, "stroke_opacity": 0.5},
    )


class CoordinateLinePairParams(BaseModel):
    first: list[float] = Field(description="[A, B, C] for Ax + By + C = 0")
    second: list[float] | None = Field(default=None, description="Optional [A, B, C] for a second line.")
    extent: float = Field(default=4.0, ge=2.0, le=10.0)
    region: str = "stage"


@component(version=1, domain="coordinate_geometry", params=CoordinateLinePairParams)
def coordinate_line_pair(p: CoordinateLinePairParams) -> Built:
    """One or two coefficient-defined lines, with the exact intersection highlighted."""
    from manim import BLUE, GREEN, RED, Dot, VGroup

    if len(p.first) != 3 or (p.second is not None and len(p.second) != 3):
        raise ToolError("each line needs [A, B, C]")
    plane = _plane(p.extent)
    def line_for(coefficients: list[float], color):
        a, b, c = coefficients
        if abs(a) + abs(b) < 1e-10:
            raise ToolError("a line must have non-zero A or B")
        if abs(b) > 1e-10:
            return plane.plot(lambda x: (-a * x - c) / b, x_range=[-p.extent, p.extent], color=color)
        x_value = -c / a
        return plane.get_vertical_line(plane.c2p(x_value, 0), color=color)
    first = line_for(p.first, BLUE)
    group = VGroup(plane, first)
    parts = {"plane": plane, "first_line": first}
    beats = [["plane"], ["first_line"]]
    if p.second is not None:
        second = line_for(p.second, GREEN)
        group.add(second)
        parts["second_line"] = second
        beats.append(["second_line"])
        a1, b1, c1 = p.first
        a2, b2, c2 = p.second
        determinant = a1 * b2 - a2 * b1
        if abs(determinant) > 1e-10:
            x_value = (b1 * c2 - b2 * c1) / determinant
            y_value = (c1 * a2 - c2 * a1) / determinant
            point = Dot(plane.c2p(x_value, y_value), color=RED, radius=0.065)
            group.add(point)
            parts["intersection"] = point
            beats.append(["intersection"])
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes="coefficients define all displayed lines")


class CircleCoordinateParams(BaseModel):
    centre: list[float]
    radius: float = Field(gt=0)
    point: list[float] | None = None
    region: str = "stage"


@component(version=1, domain="coordinate_geometry", params=CircleCoordinateParams)
def circle_coordinate_diagram(p: CircleCoordinateParams) -> Built:
    """A coordinate circle with centre, radius, and optional tangent point."""
    import numpy as np
    from manim import BLUE, RED, Circle, Dot, Line, VGroup

    if len(p.centre) != 2:
        raise ToolError("centre must be [x, y]")
    extent = max(4.0, abs(p.centre[0]) + p.radius + 1, abs(p.centre[1]) + p.radius + 1)
    plane = _plane(extent)
    centre = plane.c2p(*p.centre)
    unit = plane.c2p(p.centre[0] + 1, p.centre[1]) - centre
    circle = Circle(radius=p.radius * math.hypot(unit[0], unit[1]), color=BLUE).move_to(centre)
    centre_dot = Dot(centre, color=RED, radius=0.06)
    group = VGroup(plane, circle, centre_dot)
    parts = {"plane": plane, "circle": circle, "centre": centre_dot}
    beats = [["plane"], ["circle", "centre"]]
    if p.point is not None:
        if len(p.point) != 2 or not math.isclose(math.dist(p.point, p.centre), p.radius, rel_tol=1e-6, abs_tol=1e-6):
            raise ToolError("optional point must lie on the circle")
        point = Dot(plane.c2p(*p.point), color=RED, radius=0.06)
        radius_line = Line(centre, point.get_center(), color=RED)
        tangent_direction = (point.get_center() - centre)
        perpendicular = np.array([-tangent_direction[1], tangent_direction[0], 0.0]) * 0.5
        tangent = Line(point.get_center() + perpendicular, point.get_center() - perpendicular, color="#fbbf24")
        group.add(point, radius_line, tangent)
        parts.update({"point": point, "radius": radius_line, "tangent": tangent})
        beats.append(["point", "radius", "tangent"])
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes="radius and tangent are perpendicular at the marked point")


class CoordinateTriangleCentresParams(BaseModel):
    vertices: list[list[float]] = Field(min_length=3, max_length=3)
    region: str = "stage"


@component(version=1, domain="coordinate_geometry", params=CoordinateTriangleCentresParams)
def coordinate_triangle_centres(p: CoordinateTriangleCentresParams) -> Built:
    """A coordinate triangle with centroid and circumcentre computed from its vertices."""
    import sympy as sp
    from manim import BLUE, GREEN, ORANGE, Dot, Polygon, VGroup

    from proofmotion.tools.coordinate_geometry import coordinate_triangle_centres as solve

    result = solve(p.vertices)
    coordinates = [[float(v) for v in point] for point in p.vertices]
    extent = max(4.0, max(abs(value) for point in coordinates for value in point) + 1)
    plane = _plane(extent)
    triangle = Polygon(*[plane.c2p(*point) for point in coordinates], color=BLUE, fill_opacity=0.14)
    vertices = VGroup(*[Dot(plane.c2p(*point), color=BLUE, radius=0.055) for point in coordinates])
    centroid = Dot(plane.c2p(*[float(sp.sympify(v)) for v in result["centroid"]]), color=GREEN, radius=0.07)
    circumcentre = Dot(plane.c2p(*[float(sp.sympify(v)) for v in result["circumcentre"]]), color=ORANGE, radius=0.07)
    group = VGroup(plane, triangle, vertices, centroid, circumcentre)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts={"plane": plane, "triangle": triangle, "vertices": vertices, "centroid": centroid, "circumcentre": circumcentre}, beats=[["plane"], ["triangle", "vertices"], ["centroid", "circumcentre"]], notes="green centroid; orange circumcentre")


class CoordinateTransformationParams(BaseModel):
    original: list[list[float]]
    transformed: list[list[float]]
    region: str = "stage"


@component(version=1, domain="coordinate_geometry", params=CoordinateTransformationParams)
def coordinate_transformation(p: CoordinateTransformationParams) -> Built:
    """Original and transformed coordinate polygons, colour-coded for comparison."""
    from manim import BLUE, ORANGE, Polygon, VGroup

    if len(p.original) != len(p.transformed) or len(p.original) < 2:
        raise ToolError("original and transformed need the same number of at least two points")
    extent = max(4.0, max(abs(value) for point in [*p.original, *p.transformed] for value in point) + 1)
    plane = _plane(extent)
    original = Polygon(*[plane.c2p(*point) for point in p.original], color=BLUE, fill_opacity=0.17)
    transformed = Polygon(*[plane.c2p(*point) for point in p.transformed], color=ORANGE, fill_opacity=0.17)
    group = VGroup(plane, original, transformed)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts={"plane": plane, "original": original, "transformed": transformed}, beats=[["plane"], ["original"], ["transformed"]], notes="blue original; orange transformed")


class ConicCoordinateParams(BaseModel):
    kind: str = Field(pattern="^(circle|ellipse|parabola|hyperbola)$")
    a: float = Field(default=2.0, gt=0)
    b: float = Field(default=1.25, gt=0)
    region: str = "stage"


@component(version=1, domain="coordinate_geometry", params=ConicCoordinateParams)
def conic_coordinate_diagram(p: ConicCoordinateParams) -> Built:
    """Standard-position circle, ellipse, parabola, or hyperbola on a coordinate plane."""
    from manim import BLUE, ParametricFunction, VGroup

    extent = max(4.0, p.a + p.b + 1)
    plane = _plane(extent)
    if p.kind == "circle":
        curve = ParametricFunction(lambda t: plane.c2p(p.a * math.cos(t), p.a * math.sin(t)), t_range=[0, 2 * math.pi], color=BLUE)
    elif p.kind == "ellipse":
        curve = ParametricFunction(lambda t: plane.c2p(p.a * math.cos(t), p.b * math.sin(t)), t_range=[0, 2 * math.pi], color=BLUE)
    elif p.kind == "parabola":
        curve = plane.plot(lambda x: x**2 / (4 * p.a), x_range=[-extent, extent], color=BLUE)
    else:
        curve = VGroup(
            plane.plot(lambda x: p.b * math.sqrt(x**2 / p.a**2 - 1), x_range=[-extent, -p.a], color=BLUE),
            plane.plot(lambda x: -p.b * math.sqrt(x**2 / p.a**2 - 1), x_range=[-extent, -p.a], color=BLUE),
            plane.plot(lambda x: p.b * math.sqrt(x**2 / p.a**2 - 1), x_range=[p.a, extent], color=BLUE),
            plane.plot(lambda x: -p.b * math.sqrt(x**2 / p.a**2 - 1), x_range=[p.a, extent], color=BLUE),
        )
    group = VGroup(plane, curve)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts={"plane": plane, "conic": curve}, beats=[["plane"], ["conic"]], notes=f"standard {p.kind}")
