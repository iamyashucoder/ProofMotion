"""The components that serve every subject.

equation_chain is the one to notice: "step-by-step symbolic transformation"
appears throughout the coverage spec and was hand-written every single time.
Animating one expression becoming another is the most reused pattern there is,
and it belongs in the library rather than in each scene.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from proofmotion.components.base import Built, component
from proofmotion.layout.collision import holds_text
from proofmotion.layout.labels import place_label
from proofmotion.layout.regions import layout, place
from proofmotion.runtime.registry import ToolError
from proofmotion.components.palette import PALETTE

#: Ticks are labelled with whatever the step happens to be, so a step of
#: (high-low)/6 prints "1.3333333333333" across the axis. Rounding the step to a
#: 1/2/2.5/5 multiple is what makes the labels readable.
DECIMALS = {"num_decimal_places": 2}


def _round_step(span: float, divisions: int = 6) -> float:
    """A tick step that produces short labels."""
    if span <= 0:
        return 1.0
    rough = span / divisions
    magnitude = 10 ** math.floor(math.log10(rough))
    return next((m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= rough), magnitude * 10)
# Categorical colors for plotted series, cycled in order — distinct on
# every preset background, so they stay literal rather than themed.
SERIES = ("#4aa3df", "#f87171", "#4ade80", "#fbbf24", "#a78bfa", "#fb923c")


class EquationChainParams(BaseModel):
    steps: list[str] = Field(min_length=2, max_length=8, description="LaTeX for each stage of the rewrite.")
    labels: list[str] = Field(default_factory=list, description="Optional note beside each step after the first.")
    region: str = "stage"


@component(version=1, domain="general", params=EquationChainParams, pictorial=False)
def equation_chain(p: EquationChainParams) -> Built:
    """A sequence of expressions, each morphing into the next.

    Serves every subject: an algebraic simplification, a derivation, a chain of
    physical substitutions. `beats` gives one transform per step, so the scene
    animates the rewrite rather than cutting between finished lines.
    """
    from manim import MathTex, Text, VGroup

    stages = [MathTex(s, font_size=40) for s in p.steps]
    for stage in stages:
        place(stage, layout("title_stage_caption")[p.region], fit=True)

    parts: dict[str, Any] = {f"step_{i}": s for i, s in enumerate(stages)}
    beats = [["step_0"]]
    for index in range(1, len(stages)):
        beats.append([f"step_{index}"])

    for index, note in enumerate(p.labels[: len(stages) - 1], start=1):
        if not note:
            continue
        text = Text(note, font_size=22, color=PALETTE.highlight)
        place_label(text, stages[index], avoid=[stages[index]])
        parts[f"note_{index}"] = text
        beats[index].append(f"note_{index}")

    group = VGroup(*stages, *[v for k, v in parts.items() if k.startswith("note_")])
    return Built(
        group=group, parts=parts, beats=beats,
        notes="animate step_i -> step_{i+1} with TransformMatchingTex; only one is on screen at a time",
    )


class GeometryConstructionParams(BaseModel):
    points: dict = Field(description='Named vertices, e.g. {"A": [0, 0], "B": [3, 0], "C": [0, 4]}.')
    segments: list = Field(default_factory=list, description='Edges by name, e.g. [["A","B"], ["B","C"]].')
    mark_angles: list = Field(default_factory=list, description='Angles as [at, from, to], e.g. [["A","B","C"]].')
    show_lengths: bool = False
    region: str = "stage"


@component(version=1, domain="geometry", params=GeometryConstructionParams)
def geometry_construction(p: GeometryConstructionParams) -> Built:
    """Labelled points, segments and angle marks — the Euclidean workhorse."""
    import numpy as np
    from manim import Angle, Dot, Line, MathTex, VGroup

    if len(p.points) < 2:
        raise ToolError("at least two points are needed")
    located = {name: np.array([float(v[0]), float(v[1]), 0.0]) for name, v in p.points.items()}

    parts: dict[str, Any] = {}
    group = VGroup()
    for name, position in located.items():
        dot = Dot(position, radius=0.06, color=PALETTE.accent)
        parts[f"point_{name}"] = dot
        group.add(dot)

    segment_objects = []
    for index, (start, end) in enumerate(p.segments):
        if start not in located or end not in located:
            raise ToolError(f"segment [{start}, {end}] names a point that was not given")
        line = Line(located[start], located[end], color=PALETTE.axis, stroke_width=3)
        parts[f"segment_{index}"] = line
        segment_objects.append(line)
        group.add(line)

    beats = [[k for k in parts if k.startswith("segment_")], [k for k in parts if k.startswith("point_")]]
    beats = [b for b in beats if b]

    arcs = []
    for index, spec in enumerate(p.mark_angles):
        at, first, second = spec
        for name in (at, first, second):
            if name not in located:
                raise ToolError(f"angle names unknown point {name!r}")
        arc = Angle(Line(located[at], located[first]), Line(located[at], located[second]), radius=0.42, color=PALETTE.highlight)
        parts[f"angle_{index}"] = arc
        arcs.append(arc)
        group.add(arc)
    if arcs:
        beats.append([k for k in parts if k.startswith("angle_")])

    obstacles = [*segment_objects, *arcs]
    placed = []
    labels_row: list[str] = []
    for name, position in located.items():
        text = MathTex(name, font_size=28)
        place_label(text, position, avoid=obstacles, placed=placed)
        parts[f"label_{name}"] = text
        placed.append(text)
        group.add(text)
        labels_row.append(f"label_{name}")

    if p.show_lengths:
        for index, (start, end) in enumerate(p.segments):
            length = float(np.linalg.norm(located[end] - located[start]))
            text = MathTex(f"{length:.2f}", font_size=22, color=PALETTE.axis)
            place_label(text, (located[start] + located[end]) / 2, avoid=obstacles, placed=placed)
            parts[f"length_{index}"] = text
            placed.append(text)
            group.add(text)
            labels_row.append(f"length_{index}")

    beats.append(labels_row)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[b for b in beats if b],
                 notes=f"{len(located)} points, {len(p.segments)} segments")


def _streamline(fx, fy, x: float, y: float, extent: float, steps: int = 90) -> list[tuple[float, float]]:
    """Follow the field from a point, by small steps.

    Plain Euler is enough: the line only has to look like the arrows, and the
    step is small relative to the plot. It stops at the edge rather than
    wrapping, so a tracer never reappears somewhere it did not flow to.
    """
    step = extent / 45
    trail = [(x, y)]
    for _ in range(steps):
        try:
            vx, vy = float(fx(x, y)), float(fy(x, y))
        except (ValueError, ZeroDivisionError, TypeError, OverflowError):
            break
        speed = math.hypot(vx, vy)
        if speed < 1e-9 or not math.isfinite(speed):
            break
        x += step * vx / speed
        y += step * vy / speed
        if abs(x) > extent or abs(y) > extent:
            break
        trail.append((x, y))
    return trail


class VectorFieldParams(BaseModel):
    x_component: str = Field(description="i-component as a function of x and y, e.g. '-y'.")
    y_component: str = Field(description="j-component, e.g. 'x'.")
    extent: float = Field(default=3.0, gt=0.5, le=8.0)
    density: int = Field(default=9, ge=3, le=20, description="Arrows per axis.")
    normalize: bool = Field(default=True, description="Equal-length arrows, coloured by magnitude.")
    region: str = "stage"


@component(version=1, domain="calculus", params=VectorFieldParams)
def vector_field(p: VectorFieldParams) -> Built:
    """A vector field on a plane. Serves slope fields, E and B fields, and flows."""
    import sympy as sp
    from manim import Arrow, NumberPlane, VGroup

    x, y = sp.symbols("x y")
    try:
        fx = sp.lambdify((x, y), sp.sympify(p.x_component), "math")
        fy = sp.lambdify((x, y), sp.sympify(p.y_component), "math")
    except (SyntaxError, TypeError, ValueError) as error:
        raise ToolError(f"could not parse the field: {error}") from error

    plane = NumberPlane(
        x_range=[-p.extent, p.extent, max(p.extent / 4, 0.5)],
        y_range=[-p.extent, p.extent, max(p.extent / 4, 0.5)],
        x_length=6.4, y_length=4.4,
        background_line_style={"stroke_color": "#334155", "stroke_width": 1, "stroke_opacity": 0.5},
    )

    step = 2 * p.extent / (p.density + 1)
    arrows = VGroup()
    magnitudes = []
    for i in range(p.density):
        for j in range(p.density):
            px = -p.extent + step * (i + 1)
            py = -p.extent + step * (j + 1)
            try:
                vx, vy = float(fx(px, py)), float(fy(px, py))
            except (ArithmeticError, TypeError, ValueError):
                continue
            magnitude = math.hypot(vx, vy)
            if magnitude < 1e-9:
                continue
            magnitudes.append(magnitude)
            scale = (step * 0.42 / magnitude) if p.normalize else min(step * 0.42, magnitude * 0.2)
            tail = plane.c2p(px, py)
            head = plane.c2p(px + vx * scale, py + vy * scale)
            arrows.add(Arrow(tail, head, buff=0, stroke_width=2.4, max_tip_length_to_length_ratio=0.35, color=PALETTE.accent))

    if not len(arrows):
        raise ToolError("the field vanished everywhere on the sampled grid")

    # Tracers, so the field reads as a flow rather than a bed of nails. Each
    # path is integrated through the field the component was given, so what
    # drifts is what the arrows actually say — not a decorative loop.
    from manim import Dot, VMobject

    tracers, streams = VGroup(), []
    for seed_x, seed_y in ((-p.extent * 0.6, p.extent * 0.5), (p.extent * 0.5, -p.extent * 0.55),
                           (-p.extent * 0.5, -p.extent * 0.4)):
        trail = _streamline(fx, fy, seed_x, seed_y, p.extent)
        if len(trail) < 4:
            continue
        stream = VMobject()
        stream.set_points_smoothly([plane.c2p(sx, sy) for sx, sy in trail])
        streams.append(stream)
        tracers.add(Dot(plane.c2p(*trail[0]), radius=0.07, color=PALETTE.highlight))

    parts: dict[str, Any] = {"plane": plane, "arrows": arrows}
    group = VGroup(plane, arrows)
    if len(tracers):
        parts["tracers"] = tracers
        group.add(tracers)

    place(group, layout("title_stage_caption")[p.region])

    def drift() -> Any:
        from manim import AnimationGroup, MoveAlongPath

        return AnimationGroup(*[
            MoveAlongPath(dot, stream) for dot, stream in zip(tracers, streams, strict=False)
        ])

    return Built(
        group=group, parts=parts,
        beats=[["plane"], ["arrows"]] + ([["tracers"]] if len(tracers) else []),
        motions=[drift] if len(tracers) else [],
        notes=f"{len(arrows)} arrows, |v| from {min(magnitudes):.3g} to {max(magnitudes):.3g}",
    )


class UnitCircleParams(BaseModel):
    angle_deg: float = Field(default=45.0)
    show_sin: bool = True
    show_cos: bool = True
    show_tan: bool = False
    region: str = "stage"


@component(version=1, domain="trigonometry", params=UnitCircleParams)
def unit_circle(p: UnitCircleParams) -> Built:
    """The unit circle with sine and cosine shown as the legs they are."""
    import numpy as np
    from manim import Angle, Circle, DashedLine, Dot, Line, MathTex, VGroup

    radius = 2.0
    radians = math.radians(p.angle_deg)
    centre = np.array([0.0, 0.0, 0.0])
    point = centre + np.array([radius * math.cos(radians), radius * math.sin(radians), 0.0])

    circle = Circle(radius=radius, color=PALETTE.axis, stroke_width=3)
    horizontal = Line(centre + np.array([-radius - 0.3, 0, 0]), centre + np.array([radius + 0.3, 0, 0]),
                      stroke_width=2, color="#475569")
    vertical = Line(centre + np.array([0, -radius - 0.3, 0]), centre + np.array([0, radius + 0.3, 0]),
                    stroke_width=2, color="#475569")
    spoke = Line(centre, point, color=PALETTE.accent, stroke_width=3)
    marker = Dot(point, radius=0.075, color=PALETTE.highlight)

    parts: dict[str, Any] = {"circle": circle, "x_axis": horizontal, "y_axis": vertical,
                            "radius": spoke, "point": marker}
    group = VGroup(horizontal, vertical, circle, spoke, marker)
    beats = [["x_axis", "y_axis", "circle"], ["radius", "point"]]

    # At 0 and 180 degrees the radius lies along the baseline, and Angle needs two
    # lines that actually cross. There is also no angle worth drawing there.
    if min(p.angle_deg % 180, 180 - p.angle_deg % 180) > 0.5:
        arc = Angle(Line(centre, centre + np.array([radius, 0, 0])), spoke, radius=0.5, color=PALETTE.highlight)
        parts["angle"] = arc
        group.add(arc)
        beats[1].append("angle")

    obstacles = [circle, horizontal, vertical, spoke]
    legs_row: list[str] = []
    if p.show_cos:
        leg = DashedLine(point, np.array([0.0, point[1], 0.0]), color="#4ade80", stroke_width=2.5)
        parts["cos_leg"] = leg
        group.add(leg)
        obstacles.append(leg)
        legs_row.append("cos_leg")
    if p.show_sin:
        leg = DashedLine(point, np.array([point[0], 0.0, 0.0]), color="#f87171", stroke_width=2.5)
        parts["sin_leg"] = leg
        group.add(leg)
        obstacles.append(leg)
        legs_row.append("sin_leg")
    if legs_row:
        beats.append(legs_row)

    placed = []
    readouts = {
        "coords": (rf"(\cos\theta,\ \sin\theta)=({math.cos(radians):.2f},\ {math.sin(radians):.2f})", point),
        "angle_label": (rf"\theta={p.angle_deg:g}^\circ", centre + np.array([0.72, 0.26, 0.0])),
    }
    if p.show_tan:
        readouts["tan_label"] = (rf"\tan\theta={math.tan(radians):.2f}", point + np.array([0.0, 0.4, 0.0]))
    label_row: list[str] = []
    for key, (tex, anchor) in readouts.items():
        text = MathTex(tex, font_size=26)
        place_label(text, anchor, avoid=obstacles, placed=placed)
        parts[key] = text
        placed.append(text)
        group.add(text)
        label_row.append(key)
    beats.append(label_row)

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"cos={math.cos(radians):.6f}, sin={math.sin(radians):.6f}")


class NumberLineParams(BaseModel):
    start: float
    stop: float
    marks: dict = Field(default_factory=dict, description='Labelled positions, e.g. {"a": 1, "b": 4}.')
    interval: list = Field(default_factory=list, description="Optional [low, high] span to shade.")
    region: str = "stage"


@component(version=1, domain="general", params=NumberLineParams)
def number_line_marks(p: NumberLineParams) -> Built:
    """A number line with labelled points and an optional shaded interval."""
    from manim import Dot, Line, MathTex, NumberLine, VGroup

    if p.stop <= p.start:
        raise ToolError("stop must be greater than start")
    span = p.stop - p.start
    line = NumberLine(
        x_range=[p.start, p.stop, span / 8], length=9.0, include_numbers=True,
        color=PALETTE.axis, font_size=22,
    )
    parts: dict[str, Any] = {"line": line}
    group = VGroup(line)
    beats = [["line"]]

    if p.interval:
        low, high = float(p.interval[0]), float(p.interval[1])
        band = Line(line.n2p(low), line.n2p(high), stroke_width=8, color=PALETTE.highlight, stroke_opacity=0.5)
        parts["interval"] = band
        group.add(band)
        beats.append(["interval"])

    placed, row = [], []
    for name, position in p.marks.items():
        dot = Dot(line.n2p(float(position)), radius=0.07, color=PALETTE.accent)
        text = MathTex(name, font_size=26, color=PALETTE.accent)
        place_label(text, dot, avoid=[line, *[v for k, v in parts.items() if k != "line"]], placed=placed)
        parts[f"mark_{name}"] = dot
        parts[f"label_{name}"] = text
        placed.append(text)
        group.add(dot, text)
        row += [f"mark_{name}", f"label_{name}"]
    if row:
        beats.append(row)

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"[{p.start}, {p.stop}] with {len(p.marks)} marks")


class MatrixTransformParams(BaseModel):
    matrix: list = Field(description="2x2 matrix as [[a, b], [c, d]].")
    show_determinant: bool = True
    show_eigenvectors: bool = False
    region: str = "stage"


@component(version=1, domain="linear_algebra", params=MatrixTransformParams)
def matrix_transform(p: MatrixTransformParams) -> Built:
    """A grid and basis vectors before and after a linear map.

    The determinant shown is computed from the matrix, and the eigenvectors are
    real ones — so a scene cannot claim a rotation preserves an axis it does not.
    """
    import sympy as sp
    from manim import Arrow, MathTex, NumberPlane, VGroup

    rows = p.matrix
    if len(rows) != 2 or any(len(r) != 2 for r in rows):
        raise ToolError("matrix_transform needs a 2x2 matrix")
    a, b, c, d = (float(rows[0][0]), float(rows[0][1]), float(rows[1][0]), float(rows[1][1]))
    determinant = a * d - b * c

    plane = NumberPlane(
        x_range=[-4, 4, 1], y_range=[-3, 3, 1], x_length=6.4, y_length=4.4,
        background_line_style={"stroke_color": "#334155", "stroke_width": 1, "stroke_opacity": 0.55},
    )
    origin = plane.c2p(0, 0)
    i_hat = Arrow(origin, plane.c2p(1, 0), buff=0, stroke_width=4, color="#4ade80")
    j_hat = Arrow(origin, plane.c2p(0, 1), buff=0, stroke_width=4, color="#f87171")
    i_image = Arrow(origin, plane.c2p(a, c), buff=0, stroke_width=4, color="#4ade80")
    j_image = Arrow(origin, plane.c2p(b, d), buff=0, stroke_width=4, color="#f87171")

    parts: dict[str, Any] = {"plane": plane, "i_hat": i_hat, "j_hat": j_hat,
                            "i_image": i_image, "j_image": j_image}
    group = VGroup(plane, i_hat, j_hat, i_image, j_image)
    beats = [["plane"], ["i_hat", "j_hat"], ["i_image", "j_image"]]
    obstacles = [plane, i_hat, j_hat, i_image, j_image]

    placed, row = [], []
    if p.show_determinant:
        text = MathTex(rf"\det = {determinant:.3g}", font_size=28,
                       color="#4ade80" if determinant > 0 else "#f87171")
        place_label(text, plane.c2p(-3.2, 2.4), avoid=obstacles, placed=placed)
        parts["determinant"] = text
        placed.append(text)
        group.add(text)
        row.append("determinant")

    real_eigen = []
    if p.show_eigenvectors:
        for value, _multiplicity, vectors in sp.Matrix([[a, b], [c, d]]).eigenvects():
            if sp.im(value) != 0:
                continue
            vector = vectors[0]
            vx, vy = float(vector[0]), float(vector[1])
            norm = math.hypot(vx, vy)
            if norm < 1e-9:
                continue
            real_eigen.append(float(value))
            arrow = Arrow(origin, plane.c2p(2 * vx / norm, 2 * vy / norm), buff=0,
                          stroke_width=3, color=PALETTE.highlight)
            parts[f"eigenvector_{len(real_eigen)}"] = arrow
            group.add(arrow)
            obstacles.append(arrow)
            row.append(f"eigenvector_{len(real_eigen)}")
    if row:
        beats.append(row)

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=(
            f"det={determinant:.6g}; "
            + (f"real eigenvalues {real_eigen}" if real_eigen else "no real eigenvalues — nothing is preserved")
        ),
    )


class DistributionPlotParams(BaseModel):
    distribution: Literal["normal", "uniform", "exponential", "binomial", "poisson"] = "normal"
    parameters: list = Field(
        description=(
            "normal [mean, sigma>0]; uniform [low, high>low]; exponential [rate>0]; "
            "binomial [n>=1, 0<=p<=1]; poisson [lambda>0]."
        )
    )
    shade_from: float | None = None
    shade_to: float | None = None
    region: str = "stage"

    @model_validator(mode="after")
    def _parameters_suit_the_distribution(self) -> DistributionPlotParams:
        """`parameters` means something different for each distribution.

        Nothing checked that, so switching distribution while leaving the
        parameters alone reached the builder and died there: the normal
        default [0, 1] read as exponential gives rate 0, and 5.0 / rate raised
        ZeroDivisionError from inside the render. A component owns its own
        correctness, so this fails as a sentence the caller can act on.
        """
        needed = {"normal": 2, "uniform": 2, "exponential": 1, "binomial": 2, "poisson": 1}
        want = needed[self.distribution]
        if len(self.parameters) < want:
            raise ValueError(
                f"{self.distribution} needs {want} parameter(s), got {len(self.parameters)}: "
                f"{self.parameters}"
            )
        try:
            values = [float(v) for v in self.parameters[:want]]
        except (TypeError, ValueError) as error:
            raise ValueError(f"{self.distribution} parameters must be numbers: {self.parameters}") from error

        if self.distribution == "normal" and values[1] <= 0:
            raise ValueError(f"normal needs sigma > 0, got {values[1]}")
        if self.distribution == "uniform" and values[1] <= values[0]:
            raise ValueError(f"uniform needs high > low, got low={values[0]}, high={values[1]}")
        if self.distribution == "exponential" and values[0] <= 0:
            raise ValueError(f"exponential needs rate > 0, got {values[0]}")
        if self.distribution == "poisson" and values[0] <= 0:
            raise ValueError(f"poisson needs lambda > 0, got {values[0]}")
        if self.distribution == "binomial":
            if values[0] < 1:
                raise ValueError(f"binomial needs n >= 1, got {values[0]}")
            if not 0.0 <= values[1] <= 1.0:
                raise ValueError(f"binomial needs 0 <= p <= 1, got {values[1]}")
        return self


@component(version=1, domain="probability", params=DistributionPlotParams)
def distribution_plot(p: DistributionPlotParams) -> Built:
    """A density or mass function, with an optional shaded probability region."""
    from manim import Axes, MathTex, Rectangle, VGroup

    discrete = p.distribution in {"binomial", "poisson"}
    if discrete:
        from scipy import stats as sstats

        if p.distribution == "binomial":
            n, prob = int(p.parameters[0]), float(p.parameters[1])
            support = list(range(n + 1))
            masses = [float(sstats.binom.pmf(k, n, prob)) for k in support]
        else:
            rate = float(p.parameters[0])
            support = list(range(int(rate * 3) + 6))
            masses = [float(sstats.poisson.pmf(k, rate)) for k in support]
        axes = Axes(
            x_range=[-0.5, support[-1] + 0.5, max(1, len(support) // 8)],
            y_range=[0, max(masses) * 1.25, _round_step(max(masses) * 1.25, 4)],
            x_length=8.2, y_length=3.8, tips=False,
            axis_config={"include_numbers": True, "color": PALETTE.axis, "font_size": 20,
                         "decimal_number_config": DECIMALS},
        )
        bars = VGroup()
        width = 0.7 * (axes.c2p(1, 0)[0] - axes.c2p(0, 0)[0])
        for k, mass in zip(support, masses, strict=True):
            height = axes.c2p(0, mass)[1] - axes.c2p(0, 0)[1]
            inside = p.shade_from is not None and p.shade_to is not None and p.shade_from <= k <= p.shade_to
            bar = Rectangle(width=width, height=max(height, 1e-4),
                            color=PALETTE.highlight if inside else PALETTE.accent, fill_opacity=0.65, stroke_width=1)
            bar.move_to(axes.c2p(k, mass / 2))
            bars.add(bar)
        parts: dict[str, Any] = {"axes": axes, "bars": bars}
        group = VGroup(axes, bars)
        beats = [["axes"], ["bars"]]
        total = sum(masses)
    else:
        from scipy import stats as sstats

        if p.distribution == "normal":
            mean, sigma = float(p.parameters[0]), float(p.parameters[1])
            low, high = mean - 4 * sigma, mean + 4 * sigma
            density = lambda v: float(sstats.norm.pdf(v, mean, sigma))
        elif p.distribution == "uniform":
            low_p, high_p = float(p.parameters[0]), float(p.parameters[1])
            pad = (high_p - low_p) * 0.25
            low, high = low_p - pad, high_p + pad
            density = lambda v: float(sstats.uniform.pdf(v, low_p, high_p - low_p))
        else:
            rate = float(p.parameters[0])
            low, high = 0.0, 5.0 / rate
            density = lambda v: float(sstats.expon.pdf(v, scale=1 / rate))

        peak = max(density(low + (high - low) * t / 200) for t in range(201))
        axes = Axes(
            x_range=[low, high, _round_step(high - low)],
            y_range=[0, peak * 1.25, _round_step(peak * 1.25, 4)],
            x_length=8.2, y_length=3.8, tips=False,
            axis_config={"include_numbers": True, "color": PALETTE.axis, "font_size": 20,
                         "decimal_number_config": DECIMALS},
        )
        curve = axes.plot(density, x_range=[low, high], color=PALETTE.accent)
        parts = {"axes": axes, "curve": curve}
        group = VGroup(axes, curve)
        beats = [["axes"], ["curve"]]
        if p.shade_from is not None and p.shade_to is not None:
            shaded = axes.get_area(curve, x_range=[p.shade_from, p.shade_to], color=PALETTE.highlight, opacity=0.45)
            parts["shaded"] = shaded
            group.add(shaded)
            beats.append(["shaded"])
        total = 1.0

    label = MathTex(rf"\text{{{p.distribution}}}({', '.join(f'{v:g}' for v in p.parameters)})", font_size=26)
    place_label(label, axes.c2p(*(axes.x_range[0], 0)), avoid=list(parts.values()))
    parts["label"] = label
    group.add(label)
    beats.append(["label"])

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"{p.distribution}{tuple(p.parameters)}, mass sums to {total:.4f}")


class ArrayCellsParams(BaseModel):
    values: list = Field(min_length=1, max_length=24, description="Cell contents.")
    pointers: dict = Field(default_factory=dict, description='Named indices, e.g. {"low": 0, "mid": 3, "high": 6}.')
    highlight: list = Field(default_factory=list, description="Indices to emphasise.")
    dim: list = Field(default_factory=list, description="Indices to fade, e.g. a discarded half.")
    region: str = "stage"


@component(version=1, domain="algorithms", params=ArrayCellsParams)
def array_cells(p: ArrayCellsParams) -> Built:
    """An array as labelled cells with pointers underneath.

    The pattern behind searching, sorting, and every index-walking algorithm.
    Cells are sized and centred by the layout engine, which is what the old
    prompt rules 35 to 47 were trying and failing to achieve by instruction.
    """
    import numpy as np
    from manim import Arrow, MathTex, Rectangle, Text, VGroup

    count = len(p.values)
    cell_width = min(1.05, 11.0 / count)
    parts: dict[str, Any] = {}
    cells = VGroup()
    for index, value in enumerate(p.values):
        faded = index in p.dim
        marked = index in p.highlight
        box = Rectangle(
            width=cell_width, height=cell_width * 0.82,
            color=PALETTE.highlight if marked else PALETTE.axis,
            fill_opacity=0.35 if marked else 0.08,
            stroke_width=2.4 if marked else 1.6,
        )
        box.move_to(np.array([(index - (count - 1) / 2) * cell_width, 0.6, 0.0]))
        # A cell exists to hold its value. Without saying so, the checker reads
        # the number sitting on the cell's fill as text over geometry, which is
        # exactly what it reads a stray label on a filled disc as.
        holds_text(box)
        text = Text(str(value), font_size=int(min(26, cell_width * 26))).move_to(box.get_center())
        if faded:
            box.set_opacity(0.25)
            text.set_opacity(0.3)
        parts[f"cell_{index}"] = box
        parts[f"value_{index}"] = text
        cells.add(box, text)

    group = VGroup(cells)
    beats = [[f"cell_{i}" for i in range(count)] + [f"value_{i}" for i in range(count)]]

    # Pointers on the same or adjacent cell used to have their labels written on
    # top of each other — low, mid and high overprinted into one smear. Each
    # label claims a row, and a label whose span is already taken drops to the
    # next one, which is how a hand-drawn diagram stacks them.
    pointer_row: list[str] = []
    occupied: list[list[tuple[float, float]]] = []
    for order, (name, index) in enumerate(p.pointers.items()):
        position = int(index)
        if not 0 <= position < count:
            raise ToolError(f"pointer {name!r} points at index {position}, outside 0..{count - 1}")
        base = parts[f"cell_{position}"].get_bottom()
        colour = SERIES[order % len(SERIES)]
        text = MathTex(name, font_size=22, color=colour)
        half = max(float(text.width), 0.3) / 2 + 0.06

        row_index = 0
        while row_index < len(occupied) and any(
            base[0] - half < right and left < base[0] + half for left, right in occupied[row_index]
        ):
            row_index += 1
        if row_index == len(occupied):
            occupied.append([])
        occupied[row_index].append((base[0] - half, base[0] + half))

        drop = 0.62 + row_index * 0.46
        arrow = Arrow(base + np.array([0, -drop, 0]), base + np.array([0, -0.1, 0]),
                      buff=0, stroke_width=3.4, max_tip_length_to_length_ratio=0.4, color=colour)
        text.next_to(arrow, np.array([0.0, -1.0, 0.0]), buff=0.08)
        parts[f"pointer_{name}"] = arrow
        parts[f"pointer_label_{name}"] = text
        group.add(arrow, text)
        pointer_row += [f"pointer_{name}", f"pointer_label_{name}"]
    if pointer_row:
        beats.append(pointer_row)

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"{count} cells, {len(p.pointers)} pointers, {len(p.dim)} dimmed")
