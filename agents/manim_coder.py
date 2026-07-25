import json

from llm.base_client import LLMClient


CODER_PROMPT = """You are an expert Manim Community Edition programmer. Return Python code only. Create exactly one Scene subclass named GeneratedScene. Use only supplied verified equations. Do not import os, subprocess, socket, requests, pathlib, or use open/eval/exec. Keep content inside frame. Use Manim 0.20.1 APIs."""


def clean_code(code: str) -> str:
    return code.strip().removeprefix("```python").removeprefix("```").removesuffix("```").strip()


def fallback_code(intent: dict, tool_results: dict) -> str:
    if intent["topic"] == "gradient descent":
        values = tool_results.get("gradient_descent", [-2, 1.2, 1.84, 1.968, 1.9936])
        return f'''from manim import *

class GeneratedScene(Scene):
    def construct(self):
        title = Text("Gradient Descent", font_size=38).to_edge(UP)
        axes = Axes(x_range=[-3, 5, 1], y_range=[0, 18, 2], x_length=10, y_length=5, tips=False, axis_config={{"include_numbers": True}}).shift(DOWN * 0.4)
        labels = axes.get_axis_labels(MathTex("x"), MathTex("f(x)"))
        graph = axes.plot(lambda x: (x - 2)**2 + 1, x_range=[-2, 5], color=BLUE)
        equation = MathTex(r"f(x)=(x-2)^2+1", r"\\quad f'(x)=2(x-2)").scale(0.7).next_to(title, DOWN)
        tracker = ValueTracker({values[0]})
        dot = always_redraw(lambda: Dot(axes.c2p(tracker.get_value(), (tracker.get_value() - 2)**2 + 1), color=RED))
        minimum = Dot(axes.c2p(2, 1), color=GREEN)
        update = MathTex(r"x_{{t+1}}=x_t-\\eta f'(x_t)").scale(0.75).to_edge(DOWN)
        self.play(Write(title), Create(axes), Write(labels))
        self.play(Create(graph), Write(equation), FadeIn(dot), FadeIn(minimum))
        self.play(Write(update))
        for target in {values[1:]}:
            self.play(tracker.animate.set_value(target), run_time=0.8, rate_func=linear)
        self.play(Indicate(minimum, color=GREEN))
        self.wait(1)
'''
    return '''from manim import *

class GeneratedScene(Scene):
    def construct(self):
        title = Text("Mathematical Visualization", font_size=40)
        self.play(Write(title))
        self.wait(1)
'''


def run_manim_coder(client: LLMClient | None, state: dict) -> str:
    if client:
        request = "Verified plan and storyboard:\n" + json.dumps({"intent": state["intent"], "math_plan": state["math_plan"], "storyboard": state["storyboard"], "tool_results": state["tool_results"]}, indent=2)
        code = client.complete(CODER_PROMPT, request)
        if code:
            return clean_code(code)
    return fallback_code(state["intent"], state["tool_results"])
