from manim import *

class GeneratedScene(Scene):
    def construct(self):
        title = Text("A pretrained Transformer", font_size=42, color=WHITE).to_edge(UP, buff=0.25)
        subtitle = Text("tokens become contextual predictions", font_size=24, color=GREY_B).next_to(title, DOWN, buff=0.12)

        token_names = ["The", "model", "reads", "well"]
        ys = [-1.5, -0.5, 0.5, 1.5]

        token_nodes = VGroup(
            *[
                Circle(
                    radius=0.25,
                    color=BLUE_C,
                    stroke_width=3,
                ).move_to([-5.0, y, 0])
                for y in ys
            ]
        )
        token_labels = VGroup(
            *[
                Text(s, font_size=22, color=BLUE_B).next_to(
                    n, LEFT, buff=0.10
                )
                for s, n in zip(token_names, token_nodes)
            ]
        )
        input_caption = Text(
            "token embeddings",
            font_size=24,
            color=BLUE_C,
        ).move_to([-4.0, -2.15, 0])

        columns = [-2.6, -0.2, 2.2]
        layer_colors = [TEAL_C, GREEN_C, YELLOW_C]
        layers = []
        layer_labels = []

        for x, color, label in zip(
            columns,
            layer_colors,
            ["attention", "feed-forward", "attention"],
        ):
            nodes = VGroup(
                *[
                    Circle(
                        radius=0.2,
                        color=color,
                        fill_opacity=0.9,
                        stroke_width=2,
                    ).move_to([x, y, 0])
                    for y in ys
                ]
            )
            layers.append(nodes)
            layer_labels.append(
                Text(label, font_size=20, color=color).next_to(
                    nodes, UP, buff=0.14
                )
            )

        embed_lines = VGroup(
            *[
                Line(
                    [-4.72, y, 0],
                    [-2.8, y, 0],
                    color=BLUE_D,
                    stroke_width=2,
                )
                for y in ys
            ]
        )

        flow_lines = VGroup()
        for left, right in zip(
            [token_nodes, layers[0], layers[1]],
            [layers[0], layers[1], layers[2]],
        ):
            for i in range(4):
                flow_lines.add(
                    Line(
                        left[i].get_center(),
                        right[i].get_center(),
                        buff=0.22,
                        color=GREY_B,
                        stroke_width=1.5,
                    )
                )
                if i < 3:
                    flow_lines.add(
                        Line(
                            left[i].get_center(),
                            right[i + 1].get_center(),
                            buff=0.22,
                            color=GREY_D,
                            stroke_width=1,
                        )
                    )

        attn_arcs = VGroup()
        for nodes, color in [
            (token_nodes, BLUE_D),
            (layers[0], TEAL_D),
            (layers[2], GOLD_D),
        ]:
            for i, j, bend in [
                (0, 2, 0.8),
                (1, 3, 0.8),
                (3, 1, -0.8),
            ]:
                attn_arcs.add(
                    Line(
                        nodes[i].get_center(),
                        nodes[j].get_center(),
                        path_arc=bend,
                        buff=0.26,
                        color=color,
                        stroke_width=2,
                    )
                )

        out_x = 4.35
        out_nodes = VGroup(
            *[
                Circle(
                    radius=0.25,
                    color=PURPLE_C,
                    fill_opacity=0.9,
                    stroke_width=3,
                ).move_to([out_x, y, 0])
                for y in [1.05, 0.05, -0.95]
            ]
        )
        out_words = ["next", "token", "attention"]
        out_labels = VGroup(
            *[
                Text(word, font_size=20, color=PURPLE_B).next_to(
                    node, RIGHT, buff=0.10
                )
                for word, node in zip(out_words, out_nodes)
            ]
        )
        out_probs = VGroup(
            *[
                Text(prob, font_size=19, color=PURPLE_A).next_to(
                    node, LEFT, buff=0.10
                )
                for prob, node in zip(
                    ["0.62", "0.24", "0.14"],
                    out_nodes,
                )
            ]
        )
        out_lines = VGroup(
            *[
                Line(
                    layers[2][i].get_center(),
                    out_nodes[i % 3].get_center(),
                    buff=0.25,
                    color=PURPLE_D,
                    stroke_width=1.5,
                )
                for i in range(4)
            ]
        )
        out_caption = Text(
            "output probabilities",
            font_size=23,
            color=PURPLE_C,
        ).move_to([4.0, -2.0, 0])

        self.play(
            FadeIn(title),
            FadeIn(subtitle),
            FadeIn(token_nodes),
            FadeIn(token_labels),
            FadeIn(input_caption),
            run_time=1.5,
        )
        self.play(
            Create(embed_lines),
            FadeIn(layers[0]),
            FadeIn(layer_labels[0]),
            run_time=1.5,
        )
        self.play(
            Create(flow_lines),
            Create(attn_arcs),
            FadeIn(layers[1]),
            FadeIn(layers[2]),
            FadeIn(layer_labels[1]),
            FadeIn(layer_labels[2]),
            run_time=2.5,
        )
        self.play(
            Create(out_lines),
            FadeIn(out_nodes),
            FadeIn(out_labels),
            FadeIn(out_probs),
            FadeIn(out_caption),
            run_time=1.8,
        )
        self.wait(2.5)