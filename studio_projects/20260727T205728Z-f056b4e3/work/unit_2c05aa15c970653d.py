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
        title = Text('Projectile motion', font_size=40)
        place(title, regions['title'])
        self.play(Write(title), run_time=0.7)
        chrome.append(title)
        if stage is not None:
            self.play(FadeOut(stage), run_time=0.4)
        built = build('projectile_motion', {'speed': 20, 'angle_deg': 45, 'gravity': 9.81, 'show_components': True})
        place(built.group, regions['stage'])
        stage = built.group
        for beat in built.beats:
            parts = [built.parts[name] for name in beat if name in built.parts]
            if parts:
                self.play(*[FadeIn(p) for p in parts], run_time=1.0)
        if not built.beats:
            self.play(FadeIn(built.group), run_time=1.0)
        caption = MathTex('A projectile launched at 45^{\\circ} with speed 20\u202fm/s follows a parabolic arc.', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.0)
        chrome.append(caption)
        equation_memory = caption
        self.wait(1.6)

        leaving = chrome + ([stage] if stage is not None else [])
        if leaving:
            self.play(*[FadeOut(m) for m in leaving], run_time=0.5)
