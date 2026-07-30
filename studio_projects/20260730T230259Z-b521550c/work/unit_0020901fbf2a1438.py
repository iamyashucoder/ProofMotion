from manim import *
import numpy as np

class GeneratedScene(Scene):
    def construct(self):
        title = MathTex(
            r"\tan(x^2+y^2)=1",
            font_size=44,
        ).to_edge(UP, buff=0.35)

        axes = Axes(
            x_range=[-3.4, 3.4, 1],
            y_range=[-3.4, 3.4, 1],
            x_length=5.7,
            y_length=5.7,
            axis_config={"include_numbers": False},
            tips=True,
        ).shift(LEFT * 2.65 + DOWN * 0.15)

        axis_labels = axes.get_axis_labels(
            MathTex("x", font_size=32),
            MathTex("y", font_size=32),
        )

        origin = axes.coords_to_point(0, 0)
        radii = [
            np.sqrt(np.pi / 4 + k * np.pi)
            for k in range(4)
        ]
        scale = 5.7 / 6.8

        circles = VGroup(*[
            Circle(
                radius=radius * scale,
                color=color,
            ).move_to(origin)
            for radius, color in zip(
                radii,
                [BLUE, TEAL, GREEN, YELLOW],
            )
        ])

        spoke = Line(
            origin,
            axes.coords_to_point(
                radii[-1] * 0.707,
                radii[-1] * 0.707,
            ),
            color=WHITE,
        )
        spoke_label = MathTex(
            "r",
            font_size=32,
        ).next_to(
            spoke.get_end(),
            UP + RIGHT,
            buff=0.08,
        )

        family = MathTex(
            r"r^2=\frac{\pi}{4}+k\pi\quad(k=0,1,2,\ldots)",
            font_size=32,
        ).move_to([3.95, 2.15, 0])

        radial_form = MathTex(
            r"x^2+y^2=r^2",
            font_size=38,
        ).move_to([3.95, 0.95, 0])

        radius_form = MathTex(
            r"r=\sqrt{\frac{\pi}{4}+k\pi}",
            font_size=34,
        ).move_to([3.95, 0.05, 0])

        result = MathTex(
            r"\text{a family of concentric circles}",
            font_size=30,
        ).move_to([3.95, -1.0, 0])

        self.play(
            FadeIn(title),
            Create(axes),
            FadeIn(axis_labels),
            run_time=2,
        )
        self.play(
            FadeIn(circles),
            Create(spoke),
            FadeIn(spoke_label),
            FadeIn(family),
            run_time=2,
        )
        self.play(
            FadeIn(radial_form),
            FadeIn(radius_form),
            run_time=2,
        )
        self.play(
            FadeIn(result),
            run_time=1.5,
        )
        self.wait(2.5)