"""A clean, layout-safe rolling-sphere-on-an-incline explanation."""

from __future__ import annotations

import numpy as np
from manim import (
    BLUE,
    DOWN,
    GREEN,
    LEFT,
    ORANGE,
    RED,
    RIGHT,
    UP,
    WHITE,
    YELLOW,
    Arrow,
    Circle,
    Create,
    FadeIn,
    FadeOut,
    Line,
    MathTex,
    Scene,
    Text,
    TransformMatchingTex,
    VGroup,
)


class GeneratedScene(Scene):
    """Show force balance and the result without stacking labels or equations."""

    def construct(self) -> None:
        title = Text("Rolling sphere on an incline", font_size=38).to_edge(UP)
        incline = Line(5.6 * LEFT + 2.5 * DOWN, 5.6 * RIGHT + 0.85 * UP, color=WHITE, stroke_width=5)
        slope = np.array([1.0, 0.3, 0.0]) / np.linalg.norm([1.0, 0.3, 0.0])
        normal = np.array([-slope[1], slope[0], 0.0])
        centre = incline.point_from_proportion(0.46) + 0.56 * normal
        sphere = Circle(radius=0.56, color=BLUE, fill_color=BLUE, fill_opacity=0.35).move_to(centre)

        gravity = Arrow(centre, centre + 1.15 * DOWN, color=ORANGE, buff=0)
        gravity_label = MathTex("mg", font_size=30, color=ORANGE).move_to(centre + 1.05 * LEFT + 0.75 * DOWN)
        force_one = Arrow(centre + 0.32 * normal, centre + 1.05 * slope, color=GREEN, buff=0)
        force_two = Arrow(centre - 0.32 * normal, centre + 0.92 * slope, color=GREEN, buff=0)
        force_label = MathTex("2F", font_size=30, color=GREEN).next_to(force_one, UP, buff=0.12)
        friction = Arrow(centre - 0.56 * normal, centre - 0.75 * slope, color=RED, buff=0)
        friction_label = MathTex("f", font_size=30, color=RED).move_to(centre + 0.35 * RIGHT + 0.95 * DOWN)
        assumptions = Text("Both applied torques aid the rolling motion", font_size=24, color=YELLOW).to_edge(DOWN)
        diagram = VGroup(incline, sphere, gravity, gravity_label, force_one, force_two, force_label, friction, friction_label)

        self.play(FadeIn(title), Create(incline), Create(sphere), run_time=1.2)
        self.play(Create(gravity), FadeIn(gravity_label), Create(force_one), Create(force_two), FadeIn(force_label), run_time=1)
        self.play(Create(friction), FadeIn(friction_label), FadeIn(assumptions), run_time=0.8)
        self.wait(0.6)
        self.play(FadeOut(diagram), FadeOut(assumptions), run_time=0.6)

        equations = [
            MathTex(r"mg\sin\theta + 2F - f = ma", font_size=40),
            MathTex(r"fR + 2Fd = \frac{I a}{R}", font_size=40),
            MathTex(r"a = \frac{mg\sin\theta + 2F + 2Fd/R}{m + I/R^2}", font_size=38),
            MathTex(r"I = \frac{2}{5}mR^2,\quad m=R=F=1,\quad d=0.5", font_size=36),
            MathTex(r"\boxed{a = \frac{40}{7}\ \mathrm{m/s^2}}", font_size=48, color=YELLOW),
        ]
        current = equations[0]
        self.play(FadeIn(current), run_time=0.8)
        for following in equations[1:]:
            self.play(TransformMatchingTex(current, following), run_time=1.0)
            current = following
        result_note = Text("Acceleration down the incline", font_size=28, color=YELLOW).next_to(current, DOWN, buff=0.35)
        self.play(FadeIn(result_note), run_time=0.6)
        self.wait(1)
