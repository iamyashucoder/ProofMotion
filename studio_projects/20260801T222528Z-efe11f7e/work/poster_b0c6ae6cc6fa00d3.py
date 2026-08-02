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
        title = Text('The periodic square wave', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        if stage is not None:
            self.play(FadeOut(stage), run_time=0.4)
        built = build('function_plot', {'expr': 'sign(sin(x))', 'x_min': 0, 'x_max': 12.566370614359172, 'label': 'x(t), A=1, T=2π', 'y_min': -1.4, 'y_max': 1.4, 'region': 'stage'})
        place(built.group, regions['stage'])
        stage = built.group
        for beat in built.beats:
            parts = [built.parts[name] for name in beat if name in built.parts]
            if parts:
                self.play(reveal_all(parts, run_time=1.0))
        if not built.beats:
            self.play(reveal_all([built.group], run_time=1.0))
        for motion in built.motions:
            self.play(motion(), run_time=2.67)
        caption = MathTex('x(t)=\\begin{cases}A,&0<t<T/2\\\\-A,&T/2<t<T\\end{cases},\\qquad x(t+T)=x(t)', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.0)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 8.0 - (self.renderer.time - scene_started)))

        self.wait(0.1)
