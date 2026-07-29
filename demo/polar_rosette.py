"""A closed polar rosette: r = 10 + 4 sin(24 theta / 25)."""

from __future__ import annotations

import numpy as np
from manim import TEAL_A, UP, WHITE, YELLOW, Create, FadeIn, NumberPlane, Scene, Text, VGroup, VMobject


class PolarRosette(Scene):
    """Trace the rosette through the 25 turns required for it to close."""

    def construct(self) -> None:
        axes = NumberPlane(
            x_range=[-16, 16, 4],
            y_range=[-16, 16, 4],
            x_length=9,
            y_length=9,
            axis_config={"stroke_opacity": 0.35, "stroke_color": WHITE},
            tips=False,
        )
        axes.background_lines.set_stroke(WHITE, opacity=0.12, width=1)
        axes.faded_lines.set_stroke(WHITE, opacity=0.06, width=1)

        title = Text("Closed polar rosette", font_size=38, color=YELLOW).to_edge(UP)
        equation = Text("r = 10 + 4 sin(24θ / 25)", font_size=28, color=TEAL_A).next_to(title, direction=-UP)

        # Both the position angle and the radial oscillation repeat only after
        # theta = 50π: 25 full rotations of the plane.
        theta = np.linspace(0, 50 * np.pi, 8_001)
        radius = 10 + 4 * np.sin(24 * theta / 25)
        points = [axes.c2p(r * np.cos(t), r * np.sin(t)) for r, t in zip(radius, theta, strict=True)]
        rosette = VMobject(color=TEAL_A, stroke_width=2.25)
        rosette.set_points_as_corners(points)

        bounds = Text("6 ≤ r ≤ 14   •   closes after 25 rotations", font_size=23).next_to(axes, direction=-UP)
        labels = VGroup(title, equation, bounds)

        self.add(axes)
        self.play(FadeIn(labels, shift=UP * 0.15), run_time=0.8)
        self.play(Create(rosette, rate_func=lambda t: t), run_time=10)
        self.wait(1)
