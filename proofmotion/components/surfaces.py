"""Surfaces, seen from an angle.

"Explain gradient descent on a 3d surface" produced ten text slides, because
nothing in the catalogue could draw a loss surface — the pipeline's scenes are
plain `Scene`s, and a question that lives in three dimensions had nowhere to
go. The component here draws a pseudo-3D bowl for any f(x, y) with a fixed
oblique projection inside an ordinary 2D scene, and traces the descent down
it: the iterates, the fall in f and the early exit from the plotted region are
all computed from the expression, never taken on trust.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from proofmotion.components.base import Built, component
from proofmotion.components.palette import PALETTE
from proofmotion.layout.regions import layout, place
from proofmotion.runtime.registry import ToolError


#: The oblique projection: u = x - _UX*y, v = _VZ*z - _VY*y. The y-axis leans
#: down-left so depth reads as depth, and z is normalised into _Z_HEIGHT so a
#: steep surface and a shallow one make the same-proportioned bowl.
_UX = 0.5
_VY = 0.32
_VZ = 0.62
_Z_HEIGHT = 6.0
#: Wireframe density: curves per family, samples per curve.
_WIRES = 7
_SAMPLES = 25


class SurfaceDescentParams(BaseModel):
    """A loss surface f(x, y) and the gradient-descent path down it."""

    expr: str = Field(
        default="x**2 + 2*y**2",
        description="The loss surface, as a sympy expression in x and y, e.g. 'x**2 + 2*y**2'.",
    )
    x_range: list[float] = Field(
        default_factory=lambda: [-3.5, 3.5],
        description="Plotted x interval as [low, high], e.g. [-3.5, 3.5].",
    )
    y_range: list[float] = Field(
        default_factory=lambda: [-3.5, 3.5],
        description="Plotted y interval as [low, high], e.g. [-3.5, 3.5].",
    )
    start: list[float] = Field(
        default_factory=lambda: [3.0, 2.0],
        description="Where the descent begins, as [x, y] inside the ranges, e.g. [3.0, 2.0].",
    )
    eta: float = Field(
        default=0.1, gt=0, le=1,
        description="The learning rate in (x, y) <- (x, y) - eta * grad f.",
    )
    steps: int = Field(default=7, ge=1, le=15, description="Gradient steps to take from the start.")
    show_projection: bool = Field(
        default=True, description="Draw the floor plane and the path's shadow on it.",
    )
    region: str = "stage"

    @field_validator("x_range", "y_range")
    @classmethod
    def _ascending(cls, interval: list[float]) -> list[float]:
        if len(interval) != 2:
            raise ValueError("a range must be exactly [low, high].")
        if not interval[0] < interval[1]:
            raise ValueError(f"a range must ascend, but [{interval[0]:g}, {interval[1]:g}] does not.")
        return interval

    @model_validator(mode="after")
    def _start_on_the_surface(self) -> SurfaceDescentParams:
        if len(self.start) != 2:
            raise ValueError("start must be exactly [x, y].")
        x0, y0 = self.start
        if not (self.x_range[0] <= x0 <= self.x_range[1] and self.y_range[0] <= y0 <= self.y_range[1]):
            raise ValueError(
                f"the start ({x0:g}, {y0:g}) lies outside the plotted region "
                f"x in [{self.x_range[0]:g}, {self.x_range[1]:g}], "
                f"y in [{self.y_range[0]:g}, {self.y_range[1]:g}]; the descent must begin on the drawn surface."
            )
        return self


@component(version=1, domain="machine_learning", params=SurfaceDescentParams)
def surface_descent(p: SurfaceDescentParams) -> Built:
    """A loss surface in 3D and gradient descent rolling down it to the minimum — bowls, optimizers, learning rates.

    The surface is a wireframe under a fixed oblique projection, so it reads
    as a bowl inside an ordinary 2D scene. The gradient is differentiated
    symbolically from the expression and the iterates are computed here, so
    the path the dot rolls down is the descent the learning rate actually
    produces — including overshoot, zigzag and leaving the plotted region.
    """
    import numpy as np
    import sympy as sp
    from manim import DashedLine, Dot, Line, Polygon, VGroup, VMobject
    from sympy.parsing.sympy_parser import parse_expr

    x_sym, y_sym = sp.symbols("x y")
    try:
        expr = parse_expr(p.expr)
    except Exception as error:
        raise ToolError(f"could not parse the surface {p.expr!r}: {error}") from error
    strays = expr.free_symbols - {x_sym, y_sym}
    if strays:
        names = ", ".join(sorted(str(symbol) for symbol in strays))
        raise ToolError(f"the surface {p.expr!r} uses {names}; only x and y are allowed.")
    f = sp.lambdify((x_sym, y_sym), expr, "math")
    grad_x = sp.lambdify((x_sym, y_sym), sp.diff(expr, x_sym), "math")
    grad_y = sp.lambdify((x_sym, y_sym), sp.diff(expr, y_sym), "math")

    (x_lo, x_hi), (y_lo, y_hi) = p.x_range, p.y_range
    xs = [x_lo + (x_hi - x_lo) * i / (_SAMPLES - 1) for i in range(_SAMPLES)]
    ys = [y_lo + (y_hi - y_lo) * i / (_SAMPLES - 1) for i in range(_SAMPLES)]
    try:
        heights = [[float(f(x, y)) for x in xs] for y in ys]
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ToolError(
            f"the surface {p.expr!r} could not be evaluated over the plotted region: {error}"
        ) from error
    flat = [z for row in heights for z in row]
    if not all(math.isfinite(z) for z in flat):
        raise ToolError(f"the surface {p.expr!r} is not finite everywhere on the plotted region.")
    z_lo, z_hi = min(flat), max(flat)
    z_span = max(z_hi - z_lo, 1e-9)

    def _project(x: float, y: float, z: float) -> Any:
        """The one oblique projection everything here is drawn through."""
        clipped = min(max(z, z_lo), z_hi)
        z_norm = (clipped - z_lo) / z_span * _Z_HEIGHT
        return np.array([x - _UX * y, _VZ * z_norm - _VY * y, 0.0])

    def _wire(points: list[Any], width: float) -> Any:
        curve = VMobject(stroke_color=PALETTE.axis, stroke_width=width, stroke_opacity=0.85)
        curve.set_points_smoothly(points)
        return curve

    # Constant-x curves run front to back and carry no depth order of their
    # own; the constant-y family after them goes far to near (small y projects
    # high, large y low), so nearer strokes overdraw farther ones.
    surface = VGroup()
    x_wires = [x_lo + (x_hi - x_lo) * i / (_WIRES - 1) for i in range(_WIRES)]
    y_wires = [y_lo + (y_hi - y_lo) * i / (_WIRES - 1) for i in range(_WIRES)]
    for x_fixed in x_wires:
        surface.add(_wire([_project(x_fixed, y, float(f(x_fixed, y))) for y in ys], 1.2))
    for y_fixed in y_wires:
        surface.add(_wire([_project(x, y_fixed, float(f(x, y_fixed))) for x in xs], 1.6))

    # The floor plane sits at z = 0 (clipped into the surface's span), so for
    # a bowl it is exactly the plane the minimum touches.
    floor_z = min(max(0.0, z_lo), z_hi)
    floor = None
    if p.show_projection:
        corners = [
            _project(cx, cy, floor_z)
            for cx, cy in ((x_lo, y_lo), (x_hi, y_lo), (x_hi, y_hi), (x_lo, y_hi))
        ]
        floor = VGroup(Polygon(
            *corners, stroke_color=PALETTE.muted, stroke_width=1.2,
            stroke_opacity=0.6, fill_color=PALETTE.muted, fill_opacity=0.06,
        ))
        for i in range(1, 4):
            t = i / 4
            x_grid = x_lo + (x_hi - x_lo) * t
            y_grid = y_lo + (y_hi - y_lo) * t
            floor.add(Line(_project(x_grid, y_lo, floor_z), _project(x_grid, y_hi, floor_z),
                           stroke_color=PALETTE.muted, stroke_width=0.8, stroke_opacity=0.35))
            floor.add(Line(_project(x_lo, y_grid, floor_z), _project(x_hi, y_grid, floor_z),
                           stroke_color=PALETTE.muted, stroke_width=0.8, stroke_opacity=0.35))

    # The descent itself. Everything below is computed from the gradient, and
    # a step that leaves the plotted region ends the path rather than drawing
    # off the surface.
    iterates: list[tuple[float, float]] = [(float(p.start[0]), float(p.start[1]))]
    left_early = False
    try:
        for _ in range(p.steps):
            here_x, here_y = iterates[-1]
            next_x = here_x - p.eta * float(grad_x(here_x, here_y))
            next_y = here_y - p.eta * float(grad_y(here_x, here_y))
            if not (math.isfinite(next_x) and math.isfinite(next_y)
                    and x_lo <= next_x <= x_hi and y_lo <= next_y <= y_hi):
                left_early = True
                break
            iterates.append((next_x, next_y))
        losses = [float(f(x, y)) for x, y in iterates]
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ToolError(
            f"the gradient of {p.expr!r} could not be evaluated along the descent: {error}"
        ) from error

    on_surface = [_project(x, y, z) for (x, y), z in zip(iterates, losses, strict=True)]
    path = VGroup(*[
        Line(a, b, stroke_color=PALETTE.highlight, stroke_width=4.0)
        for a, b in pairwise(on_surface)
    ])
    points = VGroup(*[
        Dot(point, radius=0.065, color=PALETTE.highlight) for point in on_surface[1:]
    ])
    start_dot = Dot(on_surface[0], radius=0.12, color=PALETTE.highlight)

    shadow = None
    if p.show_projection:
        on_floor = [_project(x, y, floor_z) for x, y in iterates]
        shadow = VGroup(*[
            DashedLine(a, b, stroke_color=PALETTE.muted, stroke_width=2, dash_length=0.08)
            for a, b in pairwise(on_floor)
            if float(np.linalg.norm(b - a)) > 1e-3
        ])

    parts: dict[str, Any] = {"surface": surface, "path": path, "points": points, "start": start_dot}
    group = VGroup()
    if floor is not None:
        parts["floor"] = floor
        group.add(floor)
    group.add(surface)
    if shadow is not None:
        parts["shadow"] = shadow
        group.add(shadow)
    group.add(path, points, start_dot)

    # Baked in the group so every layout transform carries it, but never a
    # part and never visible: the motion reads its placed coordinates.
    track = None
    if len(on_surface) > 1:
        track = VMobject(stroke_opacity=0.0, stroke_width=1.0)
        track.set_points_as_corners(on_surface)
        group.add(track)

    place(group, layout("title_stage_caption")[p.region])

    def roll() -> Any:
        """A dot rides the computed descent path down the surface."""
        from manim import MoveAlongPath

        return MoveAlongPath(start_dot, track)

    taken = len(iterates) - 1
    walk = ", ".join(f"({x:.2f}, {y:.2f})" for x, y in iterates[1:]) or "no step stayed inside"
    return Built(
        group=group,
        parts=parts,
        beats=[["surface"]]
        + ([["floor"]] if floor is not None else [])
        + [["start"]]
        + [["path", "points"] + (["shadow"] if shadow is not None else [])],
        motions=[roll] if track is not None else [],
        notes=(
            f"{taken} steps from ({iterates[0][0]:g}, {iterates[0][1]:g}) with eta {p.eta:g}: {walk}; "
            f"f falls {losses[0]:.3g} -> {losses[-1]:.3g}"
            + (f"; the path leaves the plotted region after {taken} steps" if left_early else "")
        ),
    )
