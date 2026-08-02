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

        # ---- scene 1 ----
        scene_started = self.renderer.time
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('Adding the third harmonic', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        if stage is not None:
            self.play(FadeOut(stage), run_time=0.4)
        built = build('function_plot', {'expr': '4*(sin(x)+sin(3*x)/3)/pi', 'x_min': 0, 'x_max': 12.566370614359172, 'label': 'x₃(t), A=1, ω=1', 'y_min': -1.6, 'y_max': 1.6, 'region': 'stage'})
        place(built.group, regions['stage'])
        stage = built.group
        for beat in built.beats:
            parts = [built.parts[name] for name in beat if name in built.parts]
            if parts:
                self.play(reveal_all(parts, run_time=1.25))
        if not built.beats:
            self.play(reveal_all([built.group], run_time=1.25))
        for motion in built.motions:
            self.play(motion(), run_time=3.33)
        caption = MathTex('x_3(t)=\\frac{4A}{\\pi}\\left(\\sin(\\omega t)+\\frac{\\sin(3\\omega t)}{3}\\right)', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.25)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 10.0 - (self.renderer.time - scene_started)))

        self.wait(0.1)
