from manim import *
from proofmotion.components import build

class GeneratedScene(Scene):
    def construct(self):
        built = build(
            "function_plot",
            dict(
                expr="x**3",
                x_min=-2,
                x_max=2,
                label="y=x^3",
                region="stage",
            ),
        )

        self.play(Create(built.parts["axes"]), run_time=2.5)
        self.wait(0.5)

        self.play(Create(built.parts["curve"]), run_time=3)
        self.wait(0.5)

        self.play(
            *[Create(built.parts[name]) for name in built.beats[2]],
            run_time=2.5,
        )
        self.wait(0.5)
        self.wait(2.5)