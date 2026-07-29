"""ManimGL showcase: an illuminated, animated polar rosette.

Run with:
    manimgl demo/manimgl/advanced_polar_rosette.py GeneratedScene -w -h
"""

from __future__ import annotations

import numpy as np
from manimlib import *


class GeneratedScene(InteractiveScene):
    """Use ManimGL's real-time renderer for a layered luminous rosette."""

    def construct(self):
        display_scale = 0.22
        display_offset = DOWN * 0.45
        title = Text("Radially modulated polar rosette", font="Avenir Next", font_size=34, color=YELLOW)
        title.to_edge(UP, buff=0.35)
        # Text keeps this optional ManimGL template runnable on machines without
        # a full TeX distribution (for example, when dsfont.sty is absent).
        equation = Text("r = 10 + 4 sin(24θ / 25)", font="Avenir Next", font_size=26, color=TEAL)
        equation.set_color_by_gradient(TEAL, BLUE)
        equation.next_to(title, DOWN, buff=0.15)

        theta = ValueTracker(0)

        def point_at(t):
            radius = 10 + 4 * np.sin(24 * t / 25)
            return display_offset + display_scale * np.array([radius * np.cos(t), radius * np.sin(t), 0])

        full_curve = ParametricCurve(
            point_at,
            t_range=(0, 50 * PI, 0.05),
        )
        full_curve.set_color_by_gradient(BLUE, TEAL, GREEN, TEAL, BLUE)
        full_curve.set_stroke(width=3.25)
        tracer = always_redraw(
            lambda: VGroup(
                Dot(point_at(theta.get_value()), radius=0.25, fill_color=YELLOW, fill_opacity=0.12),
                Dot(point_at(theta.get_value()), radius=0.13, fill_color=YELLOW, fill_opacity=0.35),
                Dot(point_at(theta.get_value()), radius=0.055, fill_color=WHITE, fill_opacity=1),
            )
        )
        self.add(tracer)
        self.play(FadeIn(title, UP * 0.2), FadeIn(equation, UP * 0.15))
        self.play(ShowCreation(full_curve), theta.animate.set_value(50 * PI), run_time=10, rate_func=linear)
        self.play(FadeOut(tracer), full_curve.animate.set_stroke(width=4), run_time=0.8)
        self.wait(1)
