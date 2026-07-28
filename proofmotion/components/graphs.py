"""Graph-family components.

These four cover most of what gets asked for: plot a function, show a tangent or
secant, show accumulated area, show an iteration converging. Each derives its own
axis ranges from the function rather than accepting a guess, places its labels
with the scorer, and fits itself to a region.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.labels import place_label
from proofmotion.layout.regions import layout, place
from proofmotion.tools.numeric import numeric_sample

AXIS_COLOR = "#9aa7bd"


def tick_decimals(step: float) -> int:
    """Decimal places that suit a tick step.

    A fixed count reads the axis wrongly at both ends. An exponential plotted
    to x=15 has ticks in the millions, and one decimal place labelled them
    "3300000.0" — six digits of magnitude plus a decimal that says nothing. A
    tick step below one needs the opposite.
    """
    step = abs(step)
    if step >= 1:
        return 0
    if step >= 0.1:
        return 1
    return 2


def compact(value: float) -> str:
    """A tick label a person can read at a glance.

    Beyond five digits the number stops being read and starts being counted,
    so it is written as a power of ten instead: 800000 as 8 x 10^5.
    """
    import math

    if value == 0:
        return "0"
    magnitude = math.floor(math.log10(abs(value)))
    if -3 < magnitude < 5:
        # Four significant figures, with the trailing zeros a fixed width would
        # add taken back off: 12.5 stays 12.5 and 3.0 becomes 3.
        text = f"{value:.4g}"
        return text
    mantissa = value / (10**magnitude)
    lead = f"{mantissa:.2f}".rstrip("0").rstrip(".")
    if lead == "1":
        return f"10^{{{magnitude}}}"
    return rf"{lead} \times 10^{{{magnitude}}}"


def _nice_range(low: float, high: float, *, pad: float = 0.12) -> tuple[float, float, float]:
    """A padded range and a sensible tick step.

    Ranges chosen by a model tend to clip the interesting part of a curve or
    leave it a flat line at the bottom of the frame. Deriving them from sampled
    values removes the guess.
    """
    if high - low < 1e-9:
        low, high = low - 1, high + 1
    span = high - low
    low, high = low - span * pad, high + span * pad
    span = high - low
    rough = span / 6
    magnitude = 10 ** int(f"{rough:e}".split("e")[1])
    step = next((m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= rough), magnitude * 10)
    return low, high, step


def _axes(expr: str, x_range: tuple[float, float], y_range: tuple[float, float] | None):
    from manim import Axes

    sample = numeric_sample(expr, x_range[0], x_range[1], count=180)
    if y_range is None:
        low, high, y_step = _nice_range(sample["y_min"], sample["y_max"])
    else:
        low, high, y_step = *y_range, (y_range[1] - y_range[0]) / 6
    _, _, x_step = _nice_range(x_range[0], x_range[1], pad=0.0)
    axes = Axes(
        x_range=[x_range[0], x_range[1], x_step],
        y_range=[low, high, y_step],
        x_length=9.2,
        y_length=4.4,
        tips=False,
        axis_config={"include_numbers": True, "color": AXIS_COLOR, "font_size": 22},
        x_axis_config={"decimal_number_config": {"num_decimal_places": tick_decimals(x_step)}},
        y_axis_config={"decimal_number_config": {"num_decimal_places": tick_decimals(y_step)}},
    )
    _relabel_extremes(axes.y_axis, [low, high])
    return axes, sample


def _relabel_extremes(axis, span: list[float]) -> None:
    """Rewrite tick labels as powers of ten when the plain digits stop being read.

    Only when they do. An axis running to three decimal places or to three
    million is unreadable as digits; an axis running from 0 to 10 is perfectly
    clear and a power of ten would be pretentious.
    """
    from manim import DecimalNumber, MathTex

    biggest = max(abs(v) for v in span) or 1.0
    if 1e-3 < biggest < 1e5:
        return

    # The numbers hang in a nested group, not off the axis directly, so the
    # parent has to be found before either of them can be swapped.
    def swap(parent) -> None:
        for number in [m for m in (parent.submobjects or []) if isinstance(m, DecimalNumber)]:
            replacement = MathTex(compact(float(number.get_value())), font_size=20, color=AXIS_COLOR)
            replacement.move_to(number)
            parent.remove(number)
            parent.add(replacement)
        for child in list(parent.submobjects or []):
            if not isinstance(child, DecimalNumber | MathTex):
                swap(child)

    swap(axis)


class FunctionPlotParams(BaseModel):
    expr: str = Field(description="Function of x in Python/sympy syntax, e.g. '(x-2)**2 + 1'.")
    x_min: float
    x_max: float
    label: str | None = Field(default=None, description="LaTeX for the curve label, e.g. 'f(x)=x^2'.")
    y_min: float | None = None
    y_max: float | None = None
    region: str = "stage"


@component(version=1, domain="calculus", params=FunctionPlotParams)
def function_plot(p: FunctionPlotParams) -> Built:
    """A function graph with derived axis ranges and a non-colliding curve label."""
    from manim import BLUE, MathTex, VGroup

    y_range = (p.y_min, p.y_max) if p.y_min is not None and p.y_max is not None else None
    axes, _ = _axes(p.expr, (p.x_min, p.x_max), y_range)
    curve = axes.plot(lambda x: _f(p.expr)(x), x_range=[p.x_min, p.x_max], color=BLUE)

    parts = {"axes": axes, "curve": curve}
    group = VGroup(axes, curve)
    beats = [["axes"], ["curve"]]

    if p.label:
        text = MathTex(p.label, font_size=30)
        anchor = axes.c2p(p.x_min + (p.x_max - p.x_min) * 0.78, _f(p.expr)(p.x_min + (p.x_max - p.x_min) * 0.78))
        result = place_label(text, anchor, avoid=[axes, curve])
        parts["label"] = text
        group.add(text)
        beats.append(["label"])
        if result["leader"] is not None:
            parts["leader"] = result["leader"]
            group.add(result["leader"])
            beats[-1].append("leader")

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes="axis ranges derived from sampled values")


class TangentSecantParams(BaseModel):
    expr: str
    x_min: float
    x_max: float
    at: float = Field(description="x where the tangent touches.")
    dx: float = Field(default=0.0, description="Secant offset; 0 draws the tangent.")
    region: str = "stage"


@component(version=1, domain="calculus", params=TangentSecantParams)
def tangent_secant(p: TangentSecantParams) -> Built:
    """A curve with a tangent, or a secant when dx is non-zero."""
    from manim import BLUE, RED, YELLOW, Dot, Line, MathTex, VGroup

    axes, _ = _axes(p.expr, (p.x_min, p.x_max), None)
    f = _f(p.expr)
    curve = axes.plot(f, x_range=[p.x_min, p.x_max], color=BLUE)

    x0 = p.at
    x1 = x0 + (p.dx or 1e-4)
    slope = (f(x1) - f(x0)) / (x1 - x0)
    reach = (p.x_max - p.x_min) * 0.28
    line = Line(
        axes.c2p(x0 - reach, f(x0) - slope * reach),
        axes.c2p(x0 + reach, f(x0) + slope * reach),
        color=YELLOW, stroke_width=3,
    )
    dot = Dot(axes.c2p(x0, f(x0)), color=RED, radius=0.06)
    group = VGroup(axes, curve, line, dot)
    parts = {"axes": axes, "curve": curve, "line": line, "point": dot}
    beats = [["axes"], ["curve"], ["line", "point"]]

    kind = "secant" if p.dx else "tangent"
    text = MathTex(rf"\text{{{kind}}}:\ m={slope:.2f}", font_size=26)
    result = place_label(text, dot, avoid=[axes, curve, line])
    parts["slope_label"] = text
    group.add(text)
    beats.append(["slope_label"])
    if result["leader"] is not None:
        parts["leader"] = result["leader"]
        group.add(result["leader"])
        beats[-1].append("leader")

    if p.dx:
        second = Dot(axes.c2p(x1, f(x1)), color=RED, radius=0.06)
        parts["point2"] = second
        group.add(second)
        beats[2].append("point2")

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"slope computed numerically: {slope:.4f}")


class RiemannAreaParams(BaseModel):
    expr: str
    a: float
    b: float
    rectangles: int = Field(default=8, ge=1, le=200)
    kind: Literal["left", "right", "midpoint"] = "left"
    region: str = "stage"


@component(version=1, domain="calculus", params=RiemannAreaParams)
def riemann_area(p: RiemannAreaParams) -> Built:
    """Riemann rectangles under a curve, with the running sum shown."""
    from manim import BLUE, GREEN, MathTex, VGroup

    span = abs(p.b - p.a)
    axes, _ = _axes(p.expr, (p.a - span * 0.15, p.b + span * 0.15), None)
    f = _f(p.expr)
    curve = axes.plot(f, x_range=[p.a - span * 0.15, p.b + span * 0.15], color=BLUE)
    # Manim calls the middle sample "center"; "midpoint" is the term used when
    # teaching Riemann sums, so the parameter keeps it and translates here.
    sample_type = {"left": "left", "right": "right", "midpoint": "center"}[p.kind]
    bars = axes.get_riemann_rectangles(
        curve, x_range=[p.a, p.b], dx=(p.b - p.a) / p.rectangles,
        input_sample_type=sample_type, color=GREEN, fill_opacity=0.55, stroke_width=0.6,
    )

    width = (p.b - p.a) / p.rectangles
    offset = {"left": 0.0, "right": 1.0, "midpoint": 0.5}[p.kind]
    total = sum(f(p.a + (i + offset) * width) * width for i in range(p.rectangles))

    group = VGroup(axes, curve, bars)
    parts = {"axes": axes, "curve": curve, "rectangles": bars}
    beats = [["axes"], ["curve"], ["rectangles"]]

    text = MathTex(rf"\sum f(x_i)\,\Delta x \approx {total:.3f}", font_size=28)
    result = place_label(text, bars, avoid=[axes, curve, bars])
    parts["sum_label"] = text
    group.add(text)
    beats.append(["sum_label"])
    if result["leader"] is not None:
        parts["leader"] = result["leader"]
        group.add(result["leader"])
        beats[-1].append("leader")

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"sum computed numerically: {total:.6f}")


class IterationTraceParams(BaseModel):
    expr: str = Field(description="The function being explored, e.g. '(x-2)**2 + 1'.")
    update_rule: str = Field(description="Next value in terms of x, e.g. 'x - 0.2*2*(x-2)'.")
    start: float
    steps: int = Field(default=8, ge=1, le=60)
    x_min: float
    x_max: float
    region: str = "stage"


@component(version=1, domain="optimization", params=IterationTraceParams)
def iteration_trace(p: IterationTraceParams) -> Built:
    """A trajectory of x <- update_rule(x) walking across a curve."""
    from manim import BLUE, GREEN, RED, Dot, MathTex, VGroup

    from proofmotion.tools.numeric import numeric_iterate

    axes, _ = _axes(p.expr, (p.x_min, p.x_max), None)
    f = _f(p.expr)
    curve = axes.plot(f, x_range=[p.x_min, p.x_max], color=BLUE)
    run = numeric_iterate(p.update_rule, p.start, steps=p.steps)
    inside = [x for x in run["trajectory"] if p.x_min <= x <= p.x_max]

    dots = VGroup(*[Dot(axes.c2p(x, f(x)), color=RED, radius=0.055) for x in inside])
    group = VGroup(axes, curve, dots)
    parts = {"axes": axes, "curve": curve, "steps": dots}
    beats = [["axes"], ["curve"], ["steps"]]

    if not run["diverged"] and inside:
        final = Dot(axes.c2p(inside[-1], f(inside[-1])), color=GREEN, radius=0.08)
        parts["limit"] = final
        group.add(final)
        beats.append(["limit"])

    status = "diverges" if run["diverged"] else f"x \\to {inside[-1]:.3f}" if inside else "leaves range"
    text = MathTex(status, font_size=28)
    result = place_label(text, dots, avoid=[axes, curve, dots])
    parts["status"] = text
    group.add(text)
    beats.append(["status"])
    if result["leader"] is not None:
        parts["leader"] = result["leader"]
        group.add(result["leader"])
        beats[-1].append("leader")

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"trajectory: {[round(v, 4) for v in run['trajectory'][:12]]}")


def _f(expr: str):
    """Compile an expression to a numeric callable once per use."""
    import sympy as sp
    from sympy.parsing.sympy_parser import parse_expr

    return sp.lambdify(sp.Symbol("x"), parse_expr(expr), "math")
