from manim import *

class GeneratedScene(Scene):
    def node(self, label, center, width, color=BLUE, fs=18):
        rect = RoundedRectangle(
            corner_radius=0.1,
            width=width,
            height=0.62,
            stroke_color=color,
            fill_color=color,
            fill_opacity=0.16,
        ).move_to(center)
        text = Text(label, font_size=fs, color=WHITE).next_to(
            rect, UP, buff=0.08
        )
        return VGroup(rect, text)

    def construct(self):
        title = Text(
            "Pretrained Transformer — forward pass",
            font_size=36,
            color=YELLOW,
        ).to_edge(UP, buff=0.32)

        inp = self.node(
            "input: The cat", LEFT * 5.8 + UP * 2.35, 1.55, GREEN, 16
        )
        tok = self.node(
            "tokens", LEFT * 4.05 + UP * 2.35, 1.15, TEAL, 17
        )
        emb = self.node(
            "token + position", LEFT * 2.25 + UP * 2.35, 1.65, BLUE, 16
        )
        stack = self.node(
            "blocks × N", LEFT * 0.25 + UP * 2.35, 1.55, PURPLE, 17
        )
        final = self.node(
            "final LayerNorm", RIGHT * 2.0 + UP * 2.35, 1.7, BLUE, 16
        )
        probs = self.node(
            "next-token probabilities",
            RIGHT * 4.6 + UP * 2.35,
            1.95,
            GREEN,
            15,
        )

        arrows = [
            Arrow(
                inp[0].get_right(),
                tok[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                tok[0].get_right(),
                emb[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                emb[0].get_right(),
                stack[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                stack[0].get_right(),
                final[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                final[0].get_right(),
                probs[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
        ]

        self.play(
            FadeIn(title),
            *[
                FadeIn(n)
                for n in [inp, tok, emb, stack, final, probs]
            ],
            *[GrowArrow(a) for a in arrows],
            run_time=2.8,
        )
        self.wait(0.4)

        loaded = Text(
            "pretrained weights · fixed / loaded",
            font_size=18,
            color=ORANGE,
        ).next_to(stack[0], DOWN, buff=0.12)

        checkpoint = RoundedRectangle(
            corner_radius=0.1,
            width=1.7,
            height=0.58,
            stroke_color=ORANGE,
            fill_color=ORANGE,
            fill_opacity=0.16,
        ).move_to(LEFT * 5.15 + DOWN * 2.55)

        checkpoint_label = Text(
            "checkpoint",
            font_size=17,
            color=ORANGE,
        ).next_to(checkpoint, DOWN, buff=0.07)

        link = Arrow(
            checkpoint.get_right(),
            stack[0].get_bottom(),
            buff=0.1,
            stroke_width=3,
            color=ORANGE,
        )

        self.play(
            FadeIn(loaded),
            FadeIn(checkpoint),
            FadeIn(checkpoint_label),
            GrowArrow(link),
            run_time=1.8,
        )
        self.wait(0.35)

        block_title = Text(
            "one Transformer block expanded",
            font_size=24,
            color=WHITE,
        ).move_to(DOWN * 0.15)

        ln1 = self.node(
            "LayerNorm", LEFT * 4.3 + DOWN * 1.0, 1.35, BLUE, 16
        )
        attn = self.node(
            "multi-head attention",
            LEFT * 2.0 + DOWN * 1.0,
            1.95,
            RED,
            15,
        )
        add1 = self.node(
            "Add + residual",
            RIGHT * 0.35 + DOWN * 1.0,
            1.65,
            GREEN,
            16,
        )
        mlp = self.node(
            "feed-forward MLP",
            RIGHT * 2.7 + DOWN * 1.0,
            1.85,
            GOLD,
            15,
        )
        add2 = self.node(
            "Add + residual",
            RIGHT * 5.1 + DOWN * 1.0,
            1.65,
            GREEN,
            16,
        )

        block_arrows = [
            Arrow(
                ln1[0].get_right(),
                attn[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                attn[0].get_right(),
                add1[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                add1[0].get_right(),
                mlp[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
            Arrow(
                mlp[0].get_right(),
                add2[0].get_left(),
                buff=0.08,
                stroke_width=3,
            ),
        ]

        self.play(
            FadeIn(block_title),
            *[
                FadeIn(n)
                for n in [ln1, attn, add1, mlp, add2]
            ],
            *[GrowArrow(a) for a in block_arrows],
            run_time=2.8,
        )
        self.wait(0.35)

        vocab = self.node(
            "vocabulary projection",
            RIGHT * 5.1 + DOWN * 2.0,
            1.7,
            TEAL,
            15,
        )
        logits = self.node(
            "logits",
            RIGHT * 5.1 + DOWN * 3.0,
            1.0,
            ORANGE,
            16,
        )

        out_arrows = [
            Arrow(
                add2[0].get_right(),
                vocab[0].get_left(),
                buff=0.1,
                stroke_width=3,
            ),
            Arrow(
                vocab[0].get_bottom(),
                logits[0].get_top(),
                buff=0.08,
                stroke_width=3,
            ),
        ]

        note = Text(
            "loaded once; not updated",
            font_size=17,
            color=ORANGE,
        ).next_to(checkpoint_label, DOWN, buff=0.08)

        self.play(
            FadeIn(vocab),
            FadeIn(logits),
            FadeIn(note),
            *[GrowArrow(a) for a in out_arrows],
            run_time=2.2,
        )
        self.wait(0.7)