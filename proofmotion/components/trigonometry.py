"""Reusable diagrams for trigonometric relationships."""

from __future__ import annotations

import math

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.regions import layout, place


class TrigTriangleParams(BaseModel):
    adjacent: float = Field(gt=0)
    opposite: float = Field(gt=0)
    region: str = "stage"


@component(version=1, domain="trigonometry", params=TrigTriangleParams)
def trig_triangle(p: TrigTriangleParams) -> Built:
    """A labelled right triangle whose trig ratios come from its two legs."""
    import numpy as np
    from manim import BLUE, DOWN, GREEN, RED, RIGHT, UP, Angle, Dot, Line, MathTex, RightAngle, VGroup

    scale = min(0.9, 4.3 / max(p.adjacent, p.opposite))
    origin = np.array([-2.6, -1.6, 0.0])
    base = origin + np.array([p.adjacent * scale, 0, 0])
    top = base + np.array([0, p.opposite * scale, 0])
    horizontal, vertical, hypotenuse = Line(origin, base, color=GREEN), Line(base, top, color=RED), Line(origin, top, color=BLUE)
    right_angle = RightAngle(horizontal, vertical, length=0.24)
    theta = Angle(Line(origin, origin + np.array([1, 0, 0])), hypotenuse, radius=0.45, color="#fbbf24")
    hyp = math.hypot(p.adjacent, p.opposite)
    labels = VGroup(
        MathTex(rf"{p.adjacent:g}", font_size=26).next_to(horizontal, DOWN),
        MathTex(rf"{p.opposite:g}", font_size=26).next_to(vertical, RIGHT),
        MathTex(rf"{hyp:.3g}", font_size=26).next_to(hypotenuse, UP),
        MathTex(rf"\sin\theta={p.opposite/hyp:.3g},\quad \cos\theta={p.adjacent/hyp:.3g},\quad \tan\theta={p.opposite/p.adjacent:.3g}", font_size=25).move_to([0, -2.7, 0]),
    )
    marker = Dot(origin, radius=0.04, color="#fbbf24")
    group = VGroup(horizontal, vertical, hypotenuse, right_angle, theta, marker, labels)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts={"adjacent": horizontal, "opposite": vertical, "hypotenuse": hypotenuse, "right_angle": right_angle, "theta": theta, "labels": labels}, beats=[["adjacent", "opposite", "hypotenuse", "right_angle"], ["theta"], ["labels"]], notes="all ratios calculated from the displayed legs")


class TrigWaveParams(BaseModel):
    amplitude: float = Field(default=1.0, gt=0)
    period: float = Field(default=2 * math.pi, gt=0)
    phase_shift: float = 0.0
    vertical_shift: float = 0.0
    kind: str = Field(default="sin", pattern="^(sin|cos)$")
    region: str = "stage"


@component(version=1, domain="trigonometry", params=TrigWaveParams)
def trig_wave(p: TrigWaveParams) -> Built:
    """A sine or cosine wave with amplitude, period, phase, and midline visibly marked."""
    from manim import BLUE, GREEN, UP, Axes, DashedLine, MathTex, VGroup

    from proofmotion.components.graphs import _nice_range

    extent = 1.5 * p.period
    low, high, step = _nice_range(p.vertical_shift - p.amplitude, p.vertical_shift + p.amplitude)
    axes = Axes(x_range=[-extent, extent, p.period / 4], y_range=[low, high, step], x_length=9.0, y_length=4.5, tips=False, axis_config={"include_numbers": True, "font_size": 20, "color": "#9aa7bd"})
    frequency = 2 * math.pi / p.period
    function = (lambda x: p.vertical_shift + p.amplitude * math.sin(frequency * (x - p.phase_shift))) if p.kind == "sin" else (lambda x: p.vertical_shift + p.amplitude * math.cos(frequency * (x - p.phase_shift)))
    curve = axes.plot(function, x_range=[-extent, extent], color=BLUE)
    midline = DashedLine(axes.c2p(-extent, p.vertical_shift), axes.c2p(extent, p.vertical_shift), color=GREEN)
    label = MathTex(rf"A={p.amplitude:g},\quad T={p.period:.3g},\quad h={p.phase_shift:.3g},\quad k={p.vertical_shift:.3g}", font_size=27).next_to(axes, UP)
    group = VGroup(axes, curve, midline, label)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts={"axes": axes, "wave": curve, "midline": midline, "parameters": label}, beats=[["axes"], ["midline"], ["wave"], ["parameters"]], notes=f"{p.kind} wave with exact supplied transformation parameters")
