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
        title = Text('A Mathematical Graph', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        if stage is not None:
            self.play(FadeOut(stage), run_time=0.4)
        built = build('function_plot', {'expr': 'x^2', 'x_min': -3, 'x_max': 3})
        place(built.group, regions['stage'])
        stage = built.group
        for beat in built.beats:
            parts = [built.parts[name] for name in beat if name in built.parts]
            if parts:
                self.play(reveal_all(parts, run_time=0.8))
        if not built.beats:
            self.play(reveal_all([built.group], run_time=0.8))
        for motion in built.motions:
            self.play(motion(), run_time=2.0)
        caption = Text('The graph of f(x)=x²', font_size=30)
        caption.scale_to_fit_width(min(caption.width, regions['caption'].width))
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=0.75)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 6.0 - (self.renderer.time - scene_started)))

        leaving = chrome + ([stage] if stage is not None else [])
        if leaving:
            self.play(*[FadeOut(m) for m in leaving], run_time=0.5)
