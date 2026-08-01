"""Surfaces, seen from an angle — and curves, ridden along.

"Explain gradient descent on a 3d surface" produced ten text slides, because
nothing in the catalogue could draw a loss surface — the pipeline's scenes are
plain `Scene`s, and a question that lives in three dimensions had nowhere to
go. The components here draw pseudo-3D wireframes for any f(x, y) with a fixed
oblique projection inside an ordinary 2D scene: `surface_descent` traces
gradient descent down one, `surface_plot` draws any landscape on its own, and
`curve_motion` is the 1D cousin — a point riding a curve with its tangent.
Everything shown is computed from the expression, never taken on trust.
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


def _parse_in(expr_str: str, symbols: tuple[Any, ...], what: str) -> Any:
    """Parse a sympy expression and refuse, plainly, anything off the menu."""
    from sympy.parsing.sympy_parser import parse_expr

    try:
        expr = parse_expr(expr_str)
    except Exception as error:
        raise ToolError(f"could not parse the {what} {expr_str!r}: {error}") from error
    strays = expr.free_symbols - set(symbols)
    if strays:
        names = ", ".join(sorted(str(symbol) for symbol in strays))
        allowed = " and ".join(str(symbol) for symbol in symbols)
        verb = "are" if len(symbols) > 1 else "is"
        raise ToolError(f"the {what} {expr_str!r} uses {names}; only {allowed} {verb} allowed.")
    return expr


def _lattice(x_range: list[float], y_range: list[float]) -> tuple[list[float], list[float], list[float], list[float]]:
    """Sample positions and wire positions over the plotted rectangle."""
    (x_lo, x_hi), (y_lo, y_hi) = x_range, y_range
    xs = [x_lo + (x_hi - x_lo) * i / (_SAMPLES - 1) for i in range(_SAMPLES)]
    ys = [y_lo + (y_hi - y_lo) * i / (_SAMPLES - 1) for i in range(_SAMPLES)]
    x_wires = [x_lo + (x_hi - x_lo) * i / (_WIRES - 1) for i in range(_WIRES)]
    y_wires = [y_lo + (y_hi - y_lo) * i / (_WIRES - 1) for i in range(_WIRES)]
    return xs, ys, x_wires, y_wires


def _height_span(f: Any, xs: list[float], ys: list[float], expr_str: str) -> tuple[float, float]:
    """The surface's z extent over the grid, with the evaluation verified."""
    try:
        flat = [float(f(x, y)) for y in ys for x in xs]
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ToolError(
            f"the surface {expr_str!r} could not be evaluated over the plotted region: {error}"
        ) from error
    if not all(math.isfinite(z) for z in flat):
        raise ToolError(f"the surface {expr_str!r} is not finite everywhere on the plotted region.")
    return min(flat), max(flat)


def _projector(z_lo: float, z_hi: float) -> Any:
    """The one oblique projection everything here is drawn through."""
    import numpy as np

    z_span = max(z_hi - z_lo, 1e-9)

    def project(x: float, y: float, z: float) -> Any:
        clipped = min(max(z, z_lo), z_hi)
        z_norm = (clipped - z_lo) / z_span * _Z_HEIGHT
        return np.array([x - _UX * y, _VZ * z_norm - _VY * y, 0.0])

    return project


def _wireframe(
    f: Any, xs: list[float], ys: list[float],
    x_wires: list[float], y_wires: list[float], project: Any,
) -> Any:
    """The surface as two families of smooth curves under the projection.

    Constant-x curves run front to back and carry no depth order of their own;
    the constant-y family after them goes far to near (small y projects high,
    large y low), so nearer strokes overdraw farther ones.
    """
    from manim import VGroup, VMobject

    def wire(points: list[Any], width: float) -> Any:
        curve = VMobject(stroke_color=PALETTE.axis, stroke_width=width, stroke_opacity=0.85)
        curve.set_points_smoothly(points)
        return curve

    surface = VGroup()
    for x_fixed in x_wires:
        surface.add(wire([project(x_fixed, y, float(f(x_fixed, y))) for y in ys], 1.2))
    for y_fixed in y_wires:
        surface.add(wire([project(x, y_fixed, float(f(x, y_fixed))) for x in xs], 1.6))
    return surface


def _floor_plane(
    project: Any, x_range: list[float], y_range: list[float], floor_z: float,
) -> Any:
    """The plotted rectangle at one height, with a light interior grid."""
    from manim import Line, Polygon, VGroup

    (x_lo, x_hi), (y_lo, y_hi) = x_range, y_range
    corners = [
        project(cx, cy, floor_z)
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
        floor.add(Line(project(x_grid, y_lo, floor_z), project(x_grid, y_hi, floor_z),
                       stroke_color=PALETTE.muted, stroke_width=0.8, stroke_opacity=0.35))
        floor.add(Line(project(x_lo, y_grid, floor_z), project(x_hi, y_grid, floor_z),
                       stroke_color=PALETTE.muted, stroke_width=0.8, stroke_opacity=0.35))
    return floor


def _ascending_pair(interval: list[float]) -> list[float]:
    if len(interval) != 2:
        raise ValueError("a range must be exactly [low, high].")
    if not interval[0] < interval[1]:
        raise ValueError(f"a range must ascend, but [{interval[0]:g}, {interval[1]:g}] does not.")
    return interval


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
        return _ascending_pair(interval)

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
    from manim import DashedLine, Dot, Line, VGroup, VMobject

    x_sym, y_sym = sp.symbols("x y")
    expr = _parse_in(p.expr, (x_sym, y_sym), "surface")
    f = sp.lambdify((x_sym, y_sym), expr, "math")
    grad_x = sp.lambdify((x_sym, y_sym), sp.diff(expr, x_sym), "math")
    grad_y = sp.lambdify((x_sym, y_sym), sp.diff(expr, y_sym), "math")

    (x_lo, x_hi), (y_lo, y_hi) = p.x_range, p.y_range
    xs, ys, x_wires, y_wires = _lattice(p.x_range, p.y_range)
    z_lo, z_hi = _height_span(f, xs, ys, p.expr)
    _project = _projector(z_lo, z_hi)
    surface = _wireframe(f, xs, ys, x_wires, y_wires, _project)

    # The floor plane sits at z = 0 (clipped into the surface's span), so for
    # a bowl it is exactly the plane the minimum touches.
    floor_z = min(max(0.0, z_lo), z_hi)
    floor = _floor_plane(_project, p.x_range, p.y_range, floor_z) if p.show_projection else None

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


class SurfacePlotParams(BaseModel):
    """Any surface z = f(x, y), as a wireframe with an optional marked point."""

    expr: str = Field(
        default="sin(x)*cos(y)",
        description="The surface, as a sympy expression in x and y, e.g. 'sin(x)*cos(y)'.",
    )
    x_range: list[float] = Field(
        default_factory=lambda: [-3.0, 3.0],
        description="Plotted x interval as [low, high], e.g. [-3, 3].",
    )
    y_range: list[float] = Field(
        default_factory=lambda: [-3.0, 3.0],
        description="Plotted y interval as [low, high], e.g. [-3, 3].",
    )
    highlight_point: list[float] = Field(
        default_factory=list,
        description="An [x, y] inside the ranges to mark on the surface with a dot "
                    "and a dashed drop-line to the floor, e.g. [1.0, 0.5]; [] marks nothing.",
    )
    show_floor: bool = Field(default=True, description="Draw the floor plane under the surface.")
    region: str = "stage"

    @field_validator("x_range", "y_range")
    @classmethod
    def _ascending(cls, interval: list[float]) -> list[float]:
        return _ascending_pair(interval)

    @model_validator(mode="after")
    def _highlight_on_the_surface(self) -> SurfacePlotParams:
        if not self.highlight_point:
            return self
        if len(self.highlight_point) != 2:
            raise ValueError("highlight_point must be exactly [x, y], or [] for none.")
        hx, hy = self.highlight_point
        if not (self.x_range[0] <= hx <= self.x_range[1] and self.y_range[0] <= hy <= self.y_range[1]):
            raise ValueError(
                f"the highlight point ({hx:g}, {hy:g}) lies outside the plotted region "
                f"x in [{self.x_range[0]:g}, {self.x_range[1]:g}], "
                f"y in [{self.y_range[0]:g}, {self.y_range[1]:g}]; it must sit on the drawn surface."
            )
        return self


@component(version=1, domain="mathematics", params=SurfacePlotParams)
def surface_plot(p: SurfacePlotParams) -> Built:
    """Any surface z = f(x, y), drawn as a 3D wireframe — landscapes, saddles, waves in space.

    The same oblique projection as surface_descent, without the descent: just
    the landscape, an optional floor plane, and an optional marked point with
    its drop-line. A rotation illusion is not possible under a fixed
    projection, so the motion is honest instead: a highlight sweeps across the
    middle depth curves, or, when a point is marked, the point pulses.
    """
    import numpy as np
    import sympy as sp
    from manim import DashedLine, Dot, VGroup

    x_sym, y_sym = sp.symbols("x y")
    expr = _parse_in(p.expr, (x_sym, y_sym), "surface")
    f = sp.lambdify((x_sym, y_sym), expr, "math")

    xs, ys, x_wires, y_wires = _lattice(p.x_range, p.y_range)
    z_lo, z_hi = _height_span(f, xs, ys, p.expr)
    _project = _projector(z_lo, z_hi)
    surface = _wireframe(f, xs, ys, x_wires, y_wires, _project)

    # The floor here is the base of the plotted heights, not z = 0: an
    # arbitrary landscape has no privileged zero, and a drop-line should land
    # on the box's bottom rather than pierce the surface mid-height.
    floor_z = z_lo
    floor = _floor_plane(_project, p.x_range, p.y_range, floor_z) if p.show_floor else None

    dot = None
    drop = None
    if p.highlight_point:
        hx, hy = float(p.highlight_point[0]), float(p.highlight_point[1])
        try:
            hz = float(f(hx, hy))
        except (ArithmeticError, TypeError, ValueError) as error:
            raise ToolError(
                f"the surface {p.expr!r} could not be evaluated at ({hx:g}, {hy:g}): {error}"
            ) from error
        top = _project(hx, hy, hz)
        base = _project(hx, hy, floor_z)
        dot = Dot(top, radius=0.1, color=PALETTE.highlight)
        if float(np.linalg.norm(top - base)) > 1e-3:
            drop = DashedLine(base, top, stroke_color=PALETTE.muted, stroke_width=2, dash_length=0.08)

    parts: dict[str, Any] = {"surface": surface}
    group = VGroup()
    if floor is not None:
        parts["floor"] = floor
        group.add(floor)
    group.add(surface)
    if drop is not None:
        parts["drop"] = drop
        group.add(drop)
    if dot is not None:
        parts["point"] = dot
        group.add(dot)

    place(group, layout("title_stage_caption")[p.region])

    beats = [["surface"]]
    if floor is not None:
        beats.append(["floor"])
    if dot is not None:
        beats.append(["point"] + (["drop"] if drop is not None else []))

    if dot is not None:
        marked = dot

        def pulse() -> Any:
            """The marked point pulses, since the projection cannot rotate."""
            from manim import Indicate

            return Indicate(marked, color=PALETTE.highlight, scale_factor=1.5)

        motions = [pulse]
    else:
        def sweep() -> Any:
            """A highlight runs across the middle depth curves, front to mind."""
            from manim import Indicate, Succession

            depth_wires = surface.submobjects[len(x_wires):]
            middle = max(len(depth_wires) // 2 - 1, 0)
            chosen = depth_wires[middle:middle + 3]
            return Succession(*[
                Indicate(wire, color=PALETTE.highlight, scale_factor=1.02) for wire in chosen
            ])

        motions = [sweep]

    highlight_note = (
        f"; the point at ({p.highlight_point[0]:g}, {p.highlight_point[1]:g}) sits at "
        f"z = {float(f(*p.highlight_point)):.3g} and pulses"
        if p.highlight_point
        else "; a highlight sweeps the middle depth curves (the fixed projection cannot rotate)"
    )
    return Built(
        group=group,
        parts=parts,
        beats=beats,
        motions=motions,
        notes=(
            f"z spans {z_lo:.3g} to {z_hi:.3g} over x in [{p.x_range[0]:g}, {p.x_range[1]:g}], "
            f"y in [{p.y_range[0]:g}, {p.y_range[1]:g}]" + highlight_note
        ),
    )


class CurveMotionParams(BaseModel):
    """A curve y = f(x) and a point that rides along it."""

    expr: str = Field(
        default="sin(x) + x/2",
        description="The curve, as a sympy expression in x, e.g. 'sin(x) + x/2'.",
    )
    x_range: list[float] = Field(
        default_factory=lambda: [-4.0, 4.0],
        description="Plotted x interval as [low, high], e.g. [-4, 4].",
    )
    at: float | None = Field(
        default=None,
        description="Where the ride starts, as an x inside the range, e.g. 1.5; omitted starts at the left edge.",
    )
    show_tangent: bool = Field(
        default=True, description="Draw the tangent segment at the moving point's start.",
    )
    show_trace: bool = Field(
        default=True, description="Pre-draw a dimmed copy of the path ahead of the point.",
    )
    region: str = "stage"

    @field_validator("x_range")
    @classmethod
    def _ascending(cls, interval: list[float]) -> list[float]:
        return _ascending_pair(interval)


@component(version=1, domain="calculus", params=CurveMotionParams)
def curve_motion(p: CurveMotionParams) -> Built:
    """A point moving along a curve — sliding, tracing, with its tangent riding along; velocity shown as animation.

    The axes follow function_plot's conventions, the curve is plotted from the
    expression, and the tangent's slope is the symbolic derivative at the
    start — clipped to a fixed on-screen length so a steep curve cannot throw
    it off the frame. The motion slides the dot along the curve; the tangent
    stays put at its anchor, because riding it along would need a per-frame
    updater and emitted scenes do not use those.
    """
    import numpy as np
    import sympy as sp
    from manim import Dot, Line, VGroup

    from proofmotion.components.graphs import _axes

    x_sym = sp.Symbol("x")
    expr = _parse_in(p.expr, (x_sym,), "curve")
    f = sp.lambdify(x_sym, expr, "math")
    derivative = sp.diff(expr, x_sym)
    slope_at = sp.lambdify(x_sym, derivative, "math")

    x_lo, x_hi = float(p.x_range[0]), float(p.x_range[1])
    at = x_lo if p.at is None else float(p.at)
    if not x_lo <= at <= x_hi:
        raise ToolError(
            f"the ride starts at x = {at:g}, outside the plotted range [{x_lo:g}, {x_hi:g}]."
        )

    # Verify the whole ride is drawable before drawing any of it.
    probes = [x_lo + (x_hi - x_lo) * i / 199 for i in range(200)]
    try:
        values = [float(f(t)) for t in probes] + [float(f(at)), float(slope_at(at))]
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ToolError(
            f"the curve {p.expr!r} could not be evaluated over [{x_lo:g}, {x_hi:g}]: {error}"
        ) from error
    if not all(math.isfinite(v) for v in values):
        raise ToolError(f"the curve {p.expr!r} is not finite everywhere on [{x_lo:g}, {x_hi:g}].")

    axes, _ = _axes(p.expr, (x_lo, x_hi), None)
    curve = axes.plot(f, x_range=[x_lo, x_hi], color=PALETTE.accent, stroke_width=3.5)

    y_at = float(f(at))
    anchor = np.array(axes.c2p(at, y_at))
    dot = Dot(anchor, radius=0.09, color=PALETTE.highlight)

    # A dimmed, wider stroke under the curve marking the stretch the dot will
    # ride — drawn beneath the accent curve so it reads as the road ahead.
    trace = None
    if p.show_trace and x_hi - at > 1e-6:
        trace = axes.plot(
            f, x_range=[at, x_hi], color=PALETTE.muted, stroke_width=7, stroke_opacity=0.3,
        )

    # The tangent, clipped to a fixed on-screen length centred on the dot: the
    # direction comes from the symbolic derivative, expressed in scene
    # coordinates so the drawn slope matches the plotted curve exactly.
    tangent = None
    slope = float(slope_at(at))
    if p.show_tangent:
        along = np.array(axes.c2p(at + 1.0, y_at + slope)) - anchor
        along = along / float(np.linalg.norm(along))
        half = 1.1
        tangent = Line(
            anchor - along * half, anchor + along * half,
            stroke_color=PALETTE.secondary, stroke_width=3,
        )

    parts: dict[str, Any] = {"axes": axes, "curve": curve, "dot": dot}
    group = VGroup(axes)
    if trace is not None:
        parts["trace"] = trace
        group.add(trace)
    group.add(curve)
    if tangent is not None:
        parts["tangent"] = tangent
        group.add(tangent)
    group.add(dot)

    # The invisible track the motion follows: the stretch from the start of
    # the ride to the right edge, baked into the group so placement carries it.
    track = None
    if x_hi - at > 1e-6:
        track = axes.plot(f, x_range=[at, x_hi], stroke_opacity=0.0, stroke_width=1.0)
        group.add(track)

    place(group, layout("title_stage_caption")[p.region])

    beats = [
        ["axes"],
        ["curve"] + (["trace"] if trace is not None else []),
        ["dot"] + (["tangent"] if tangent is not None else []),
    ]

    def slide() -> Any:
        """The dot rides the curve from its start to the right edge."""
        from manim import MoveAlongPath

        return MoveAlongPath(dot, track)

    tangent_note = (
        f"; tangent slope f'({at:g}) = {slope:.3g}, drawn at a fixed on-screen length; "
        "the tangent stays at its anchor — riding it along the curve needs a per-frame "
        "updater, which emitted scenes do not use, so the dot rides alone"
        if tangent is not None
        else ""
    )
    if track is not None:
        ride_note = f"the dot rides the curve from x = {at:g} to x = {x_hi:g}"
        motions = [slide]
    else:
        ride_note = f"the ride starts at the right edge x = {x_hi:g}, so there is nowhere to go and no motion"
        motions = []
    return Built(
        group=group,
        parts=parts,
        beats=beats,
        motions=motions,
        notes=ride_note + tangent_note,
    )
