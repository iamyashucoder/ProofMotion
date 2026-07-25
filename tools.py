from pathlib import Path
import subprocess
import sys


def generate_template_code(animation_type):
    """
    Returns Manim Python code according to the detected animation type.
    """

    if animation_type == "circle_to_square":
        return '''
from manim import *


class GeneratedScene(Scene):
    def construct(self):
        circle = Circle()
        square = Square()

        self.play(Create(circle))
        self.wait(1)

        self.play(Transform(circle, square))
        self.wait(1)
'''

    elif animation_type == "text_animation":
        return '''
from manim import *


class GeneratedScene(Scene):
    def construct(self):
        text = Text("Welcome to Manim Agent")

        self.play(Write(text))
        self.wait(1)

        self.play(text.animate.scale(1.5))
        self.wait(1)

        self.play(FadeOut(text))
'''

    elif animation_type == "math_animation":
        return r'''
from manim import *


class GeneratedScene(Scene):
    def construct(self):
        equation = MathTex(r"E = mc^2")

        self.play(Write(equation))
        self.wait(1)

        self.play(equation.animate.scale(1.5))
        self.wait(1)
'''

    else:
        return '''
from manim import *


class GeneratedScene(Scene):
    def construct(self):
        message = Text("Sorry, this animation is not supported yet.")
        message.scale(0.7)

        self.play(Write(message))
        self.wait(2)
'''


def save_manim_code(code, filename="generated_scene.py"):
    """
    Saves generated Manim code into a Python file.
    """

    file_path = Path(filename)
    file_path.write_text(code, encoding="utf-8")

    return file_path


def render_manim_scene(
    file_path,
    scene_name="GeneratedScene",
):
    """
    Renders the generated Manim scene.
    """

    command = [
        "manim",
        "-ql",
        str(file_path),
        scene_name,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    return result
def clean_generated_code(code):
    """
    Removes Markdown code fences from LLM output.
    """

    code = code.strip()

    if code.startswith("```python"):
        code = code[len("```python"):]

    elif code.startswith("```"):
        code = code[len("```"):]

    if code.endswith("```"):
        code = code[:-3]

    return code.strip()
import ast


def validate_python_code(code):
    """
    Checks whether the generated Python code has valid syntax.
    """

    try:
        ast.parse(code)
        return True, None

    except SyntaxError as error:
        return False, str(error)

def render_manim_scene(
    file_path,
    scene_name="GeneratedScene",
    timeout_seconds=120,
):
    command = [
        sys.executable,
        "-m",
        "manim",
        "-ql",
        str(file_path),
        scene_name,
    ]

    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )

    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=f"Rendering timed out after {timeout_seconds} seconds.",
        )