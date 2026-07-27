from manim import *

from proofmotion.components import build
from proofmotion.layout.regions import layout, place


class GeneratedScene(Scene):
    def construct(self):
        regions = layout('title_stage_caption')
        chrome = []
        stage = None
        equation_memory = None

        # ---- scene 1 ----
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('Sign function on x²', font_size=40)
        place(title, regions['title'])
        self.play(Write(title), run_time=0.7)
        chrome.append(title)
        if stage is not None:
            self.play(FadeOut(stage), run_time=0.4)
        built = build('function_plot', {'expr': 'sign(x)', 'x_min': -5, 'x_max': 5, 'label': '\\operatorname{sgn}(x)', 'y_min': -1.5, 'y_max': 1.5})
        place(built.group, regions['stage'])
        stage = built.group
        for beat in built.beats:
            parts = [built.parts[name] for name in beat if name in built.parts]
            if parts:
                self.play(*[FadeIn(p) for p in parts], run_time=0.75)
        if not built.beats:
            self.play(FadeIn(built.group), run_time=0.75)
        caption = MathTex('The sign function sgn(x) is -1 for x<0, 0 at x=0, and +1 for x>0.', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=0.75)
        chrome.append(caption)
        equation_memory = caption
        self.wait(1.2)

        leaving = chrome + ([stage] if stage is not None else [])
        if leaving:
            self.play(*[FadeOut(m) for m in leaving], run_time=0.5)
