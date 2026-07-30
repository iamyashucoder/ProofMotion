from manim import *

class GeneratedScene(Scene):
    def construct(self):
        axes = Axes(
            x_range=[-2, 2, 1],
            y_range=[-3, 3, 1],
            x_length=10,
            y_length=5.4,
            axis_config={"include_numbers": True, "font_size": 24},
        )
        axes.shift(DOWN * 0.25)

        axis_labels = axes.get_axis_labels(
            x_label=MathTex("x"),
            y_label=MathTex("y"),
        )
        title = Text("A graph becomes a route", font_size=42).to_edge(UP)

        graph = axes.plot(
            lambda x: x**3,
            x_range=[-1.442, 1.442],
            color=YELLOW,
            stroke_width=6,
        )
        graph_label = (
            MathTex("y=x^3", font_size=30, color=YELLOW)
            .move_to(axes.c2p(0.9, 2.15))
            .shift(RIGHT * 0.25)
        )

        self.play(
            Create(axes),
            FadeIn(axis_labels),
            FadeIn(title),
            run_time=1.5,
        )
        self.play(
            Create(graph),
            FadeIn(graph_label),
            run_time=1.5,
        )
        self.wait(0.5)

        road = axes.plot(
            lambda x: x**3,
            x_range=[-1.442, 1.442],
            color=GRAY,
            stroke_width=24,
        )
        road_mark = axes.plot(
            lambda x: x**3,
            x_range=[-1.442, 1.442],
            color=YELLOW,
            stroke_width=3,
        )
        path_label = Text(
            "the graph is now the motion path",
            font_size=28,
            color=WHITE,
        ).move_to(DOWN * 2.65)

        self.play(
            Transform(graph, road),
            FadeOut(graph_label),
            Create(road_mark),
            FadeIn(path_label),
            run_time=2,
        )
        self.wait(0.5)

        body = RoundedRectangle(
            corner_radius=0.12,
            width=0.95,
            height=0.48,
            color=BLUE,
            fill_color=BLUE,
            fill_opacity=1,
        )
        roof = Rectangle(
            width=0.68,
            height=0.16,
            color=BLUE,
            fill_color=BLUE,
            fill_opacity=1,
        ).next_to(body, UP, buff=0)

        window1 = Rectangle(
            width=0.19,
            height=0.13,
            color=WHITE,
            fill_color=WHITE,
            fill_opacity=1,
        )
        window2 = window1.copy()
        window1.move_to(body.get_center() + LEFT * 0.23 + UP * 0.08)
        window2.move_to(body.get_center() + RIGHT * 0.23 + UP * 0.08)

        wheel1 = Circle(
            radius=0.105,
            color=BLACK,
            fill_color=BLACK,
            fill_opacity=1,
        )
        wheel2 = wheel1.copy()
        wheel1.move_to(body.get_center() + LEFT * 0.28 + DOWN * 0.27)
        wheel2.move_to(body.get_center() + RIGHT * 0.28 + DOWN * 0.27)

        bus = VGroup(body, roof, window1, window2, wheel1, wheel2)
        bus.move_to(road.get_start())

        bus_label = Text(
            "BUS",
            font_size=20,
            color=WHITE,
        ).next_to(body, UP, buff=0.3)
        bus.add(bus_label)

        self.play(FadeIn(bus), run_time=0.7)
        self.play(
            MoveAlongPath(bus, road, rate_func=linear),
            run_time=3.5,
        )
        self.wait(1.0)