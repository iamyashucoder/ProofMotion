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
        carried = build('comparison', {'left_title': 'Time domain', 'right_title': 'Frequency domain', 'rows': [['repeating square waveform', 'harmonic spikes'], ['horizontal axis: time t', 'horizontal axis: frequency'], ['vertical axis: x(t)', 'vertical axis: amplitude']], 'row_labels': ['picture', 'horizontal axis', 'vertical quantity'], 'highlight': [0]})
        place(carried.group, regions['stage'])
        self.add(carried.group)
        stage = carried.group

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

        # ---- scene 2 ----
        scene_started = self.renderer.time
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('Finding the fundamental', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        built = build('function_plot', {'expr': '2*pi/x', 'x_min': 0.5, 'x_max': 10, 'label': 'ω(T)=2π/T', 'y_min': 0, 'y_max': 13, 'region': 'stage'})
        place(built.group, regions['stage'])
        self.play(ReplacementTransform(stage, built.group), run_time=2.24)
        stage = built.group
        for motion in built.motions:
            self.play(motion(), run_time=3.0)
        caption = MathTex('\\omega=\\frac{2\\pi}{T}', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.12)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 9.0 - (self.renderer.time - scene_started)))

        # ---- scene 3 ----
        scene_started = self.renderer.time
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('The first harmonic', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        built = build('function_plot', {'expr': '4*sin(x)/pi', 'x_min': 0, 'x_max': 12.566370614359172, 'label': 'x₁(t), A=1, ω=1', 'y_min': -1.5, 'y_max': 1.5, 'region': 'stage'})
        place(built.group, regions['stage'])
        self.play(ReplacementTransform(stage, built.group), run_time=2.24)
        stage = built.group
        for motion in built.motions:
            self.play(motion(), run_time=3.0)
        caption = MathTex('x_1(t)=\\frac{4A}{\\pi}\\sin(\\omega t)', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.12)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 9.0 - (self.renderer.time - scene_started)))

        # ---- scene 4 ----
        scene_started = self.renderer.time
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('Adding the third harmonic', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        built = build('function_plot', {'expr': '4*(sin(x)+sin(3*x)/3)/pi', 'x_min': 0, 'x_max': 12.566370614359172, 'label': 'x₃(t), A=1, ω=1', 'y_min': -1.6, 'y_max': 1.6, 'region': 'stage'})
        place(built.group, regions['stage'])
        self.play(ReplacementTransform(stage, built.group), run_time=2.5)
        stage = built.group
        for motion in built.motions:
            self.play(motion(), run_time=3.33)
        caption = MathTex('x_3(t)=\\frac{4A}{\\pi}\\left(\\sin(\\omega t)+\\frac{\\sin(3\\omega t)}{3}\\right)', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.25)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 10.0 - (self.renderer.time - scene_started)))

        # ---- scene 5 ----
        scene_started = self.renderer.time
        if chrome:
            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)
            chrome = []
            equation_memory = None
        title = Text('More odd harmonics', font_size=40)
        place(title, regions['title'])
        self.play(Write(title, run_time=0.7))
        chrome.append(title)
        built = build('function_plot', {'expr': '4*(sin(x)+sin(3*x)/3+sin(5*x)/5+sin(7*x)/7)/pi', 'x_min': 0, 'x_max': 12.566370614359172, 'label': 'x₇(t), A=1, ω=1', 'y_min': -1.6, 'y_max': 1.6, 'region': 'stage'})
        place(built.group, regions['stage'])
        self.play(ReplacementTransform(stage, built.group), run_time=3.0)
        stage = built.group
        for motion in built.motions:
            self.play(motion(), run_time=4.0)
        caption = MathTex('x_7(t)=\\frac{4A}{\\pi}\\left(\\sin(\\omega t)+\\frac{\\sin(3\\omega t)}{3}+\\frac{\\sin(5\\omega t)}{5}+\\frac{\\sin(7\\omega t)}{7}\\right)', font_size=30)
        place(caption, regions['caption'])
        self.play(Write(caption), run_time=1.5)
        chrome.append(caption)
        equation_memory = caption
        self.wait(max(0.4, 12.0 - (self.renderer.time - scene_started)))

        leaving = chrome
        if leaving:
            self.play(*[FadeOut(m) for m in leaving], run_time=0.5)
        self.wait(0.15)
