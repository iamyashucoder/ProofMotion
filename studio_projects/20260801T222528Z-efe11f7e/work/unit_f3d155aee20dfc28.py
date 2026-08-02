from manim import *

from proofmotion.components import build
from proofmotion.components.palette import activate
from proofmotion.layout.preamble import ensure_packages
from proofmotion.layout.regions import layout, place
from proofmotion.layout.reveal import reveal_all

ensure_packages()
activate('dark')


class GeneratedScene(Scene):
    def construct(self):
        regions = layout('title_stage_caption')
        chrome = []
        stage = None
        equation_memory = None

        # the previous clip's figure, standing where it stood
        carried = build('partial_sums', {'terms': [1, 0.3333333333333333, 0.2, 0.14285714285714285, 0.1111111111111111], 'limit': 1.5707963267948966, 'label': 'S_N: Σ 1/(2m+1)', 'region': 'stage'})
        place(carried.group, regions['stage'])
        self.add(carried.group)
        stage = carried.group

        # ---- scene 1 ----
        scene_started = self.renderer.time
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('A term becomes a spike', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        if stage is not None:
            self.play(FadeOut(stage), run_time=0.4)
        built = build('function_plot', {'expr': '4/(pi*(2*x+1))', 'x_min': 0, 'x_max': 7, 'label': 'amplitude = 4A/[π(2m+1)], A=1', 'y_min': 0, 'y_max': 1.5, 'region': 'stage'})
        place(built.group, regions['stage'])
        stage = built.group
        for beat in built.beats:
            parts = [built.parts[name] for name in beat if name in built.parts]
            if parts:
                self.play(reveal_all(parts, run_time=1.12))
        if not built.beats:
            self.play(reveal_all([built.group], run_time=1.12))
        for motion in built.motions:
            self.play(motion(), run_time=3.0)
        caption = MathTex('\\text{frequency of term }m=(2m+1)\\omega,\\qquad \\text{amplitude of term }m=\\frac{4A}{\\pi(2m+1)}', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.12)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 9.0 - (self.renderer.time - scene_started)))

        leaving = chrome
        if leaving:
            self.play(*[FadeOut(m) for m in leaving], run_time=0.5)
        self.wait(0.15)
