"""Emit a scene from chosen components, deterministically.

Composition was a suggestion in the coder's prompt, and the measurements said
so: 29% across the whole history, and not once in the last ten runs. A prompt
cannot make it structural. This can.

The model still decides what a scene means — which component expresses the idea,
with what parameters. Python decides everything after that: reveal order,
titles, captions, and clearing the stage between sections. Rules that used to be
prose the coder could ignore are now emitted code that runs the same way every
time.

The output is source rather than a live scene deliberately. It renders through
the same path, the same checkers inspect it, and it stays editable.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from proofmotion.components import COMPONENTS
from proofmotion.layout.notation import looks_like_maths, mixes_prose, to_latex, unsupported
from proofmotion.runtime.registry import ToolError
from schemas.storyboard import MAX_SCENES

def _header(style: str) -> str:
    # activate() runs before the scene class exists, so the background and the
    # text defaults are set by the time Manim draws anything — that is what
    # restyles fifty-odd components without any of them naming a color twice.
    return f'''from manim import *

from proofmotion.components import build
from proofmotion.components.palette import activate
from proofmotion.layout.preamble import ensure_packages
from proofmotion.layout.regions import layout, place
from proofmotion.layout.reveal import reveal_all

ensure_packages()
activate({style!r})


class GeneratedScene(Scene):
    def construct(self):
'''


class SceneAssignment(BaseModel):
    """One storyboard scene, mapped onto a component."""

    title: str = Field(default="", description="Short heading for this scene, or empty for none.")
    component: str | None = Field(
        default=None,
        description="Component name from component_search, or null when no component fits.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for that component."
    )
    caption: str = Field(
        default="", description="LaTeX shown beneath the stage (no $ delimiters), or empty."
    )
    read_from_previous: list[str] = Field(default_factory=list, description="Selected board items retained from the preceding scene.")
    bridge_text: str = Field(default="", description="Short visual connection from the retained board item to this step.")
    forget_after: list[str] = Field(default_factory=list, description="Board items cleared after this step is read.")
    seconds: float = Field(default=6.0, gt=0.5, le=40.0, description="Target length of this scene.")
    narration: str = Field(
        default="",
        description="One or two sentences read aloud over this scene. Spoken, never shown on screen.",
    )
    #: Hand corrections applied after the layout engine has placed everything.
    #: A checker can measure that a label overlaps; it cannot know the label
    #: reads better slightly left. See PLAN-STUDIO §7.
    overrides: dict[str, Any] = Field(default_factory=dict)


class ScenePlan(BaseModel):
    assignments: list[SceneAssignment] = Field(min_length=1, max_length=MAX_SCENES)


def coverage(plan: ScenePlan) -> float:
    """Fraction of scenes a component can express."""
    if not plan.assignments:
        return 0.0
    return sum(1 for a in plan.assignments if a.component) / len(plan.assignments)


def pictorial_coverage(plan: ScenePlan) -> float:
    """Fraction of scenes that actually draw something.

    `coverage` counts any component, and equation_chain is a component — so a
    question asking for full diagrams came back as four screens of algebra with
    a coverage of 0.75. What makes an explanation visual is pictures, and this
    is the number that says whether there are any.
    """
    if not plan.assignments:
        return 0.0
    drawn = sum(
        1
        for a in plan.assignments
        if a.component and getattr(COMPONENTS.get(a.component), "pictorial", True)
    )
    return drawn / len(plan.assignments)


def check(plan: ScenePlan) -> list[str]:
    """Everything wrong with the plan, before a line of code is emitted.

    Parameters are validated against each component's own model here rather than
    at render time, so a wrong parameter comes back as a sentence the selector
    can act on instead of a traceback twenty seconds into a render.
    """
    problems: list[str] = []
    for index, scene in enumerate(plan.assignments, 1):
        if not scene.component:
            # A scene with no picture is still a scene: an equation on screen
            # under a heading. Refusing the whole plan over one of those sent
            # a run with 3 of 4 scenes mapped down the slow path and produced
            # a worse video than assembling it would have. What is not
            # acceptable is a scene with nothing in it at all.
            if not scene.caption and not scene.title:
                problems.append(f"scene {index}: no component, and no title or caption to show")
            continue
        spec = COMPONENTS.get(scene.component)
        if spec is None:
            problems.append(
                f"scene {index}: unknown component {scene.component!r}; "
                f"available: {sorted(COMPONENTS)}"
            )
            continue
        try:
            spec.params.model_validate(scene.parameters)
        except Exception as error:  # noqa: BLE001 - pydantic's message is the report
            problems.append(f"scene {index}: {scene.component} parameters rejected: {error}")
    return problems


def _nudge(name: str, overrides: dict[str, Any]) -> list[str]:
    """Emit the hand corrections for one placed object, if there are any.

    Applied after `place`, so an override moves what the engine decided rather
    than fighting it. Nothing here guesses: an override exists only because a
    person dragged something.
    """
    lines: list[str] = []
    shift = (overrides.get("shift") or {}).get(name) or {}
    dx, dy = float(shift.get("dx", 0.0)), float(shift.get("dy", 0.0))
    if dx or dy:
        lines.append(f"        {name}.shift(RIGHT * {dx} + UP * {dy})")
    scale = (overrides.get("scale") or {}).get(name)
    if scale:
        lines.append(f"        {name}.scale({float(scale)})")
    return lines


def assemble(plan: ScenePlan, *, style: str = "dark") -> str:
    """Turn chosen components into complete, runnable source.

    Raises when the plan does not fully check out. A half-assembled scene would
    be worse than either path, so the caller falls back to the coder instead.
    """
    problems = check(plan)
    if problems:
        raise ToolError("; ".join(problems))

    lines: list[str] = []
    write = lines.append
    write("        regions = layout('title_stage_caption')")
    # The stage and the words around it are cleared on different schedules. The
    # title and caption change every scene; the picture only changes when it
    # actually differs, so a run of scenes about one figure keeps it on screen.
    write("        chrome = []")
    write("        stage = None")
    write("        equation_memory = None")
    write("")

    standing: tuple[str, str] | None = None
    for index, scene in enumerate(plan.assignments, 1):
        write(f"        # ---- scene {index} ----")
        # The clock this scene settles against: `seconds` is a floor, not a
        # guess. The scene used to end when its animations did plus a fifth of
        # its budget, so a slide asked to hold for its narration simply didn't
        # — the voice ran on into the next slide's picture.
        write("        scene_started = self.renderer.time")
        read_equation = "equation" in scene.read_from_previous
        # Selective read/forget: the new board retains only items explicitly
        # requested by this scene. Every other item is removed before writing.
        write("        if chrome:")
        if read_equation:
            write("            forgotten = [m for m in chrome if m is not equation_memory]")
            write("            if forgotten:")
            write("                self.play(*[FadeOut(m) for m in forgotten], run_time=0.4)")
            write("            chrome = [equation_memory] if equation_memory is not None else []")
        else:
            write("            self.play(*[FadeOut(m) for m in chrome], run_time=0.4)")
            write("            chrome = []")
            write("            equation_memory = None")

        if scene.title:
            write(f"        title = Text({scene.title!r}, font_size=40)")
            write("        place(title, regions['title'])")
            lines.extend(_nudge("title", scene.overrides))
            write("        self.play(Write(title, run_time=0.7))")
            write("        chrome.append(title)")

        beat_time = max(0.4, round(scene.seconds / 8, 2))
        key = (scene.component, repr(scene.parameters)) if scene.component else None
        if "diagram" in scene.read_from_previous and key is not None and key == standing:
            # Identical picture, identical parameters. Rebuilding it means the
            # viewer watches the same figure fade out and back in for no reason
            # — four times over, in the run that prompted this. Leave it up and
            # let the words change around it.
            write("        # unchanged from the previous scene; left on screen")
        elif scene.component and standing and standing[0] == scene.component:
            # Same figure, different numbers: the rectangles get narrower, the
            # tangent slides along the curve. Fading one out and the next in
            # shows two pictures; transforming between them shows the thing
            # happening, which is the whole reason to animate this rather than
            # print it. This is where the motion is.
            write(f"        built = build({scene.component!r}, {scene.parameters!r})")
            write("        place(built.group, regions['stage'])")
            write(f"        self.play(Transform(stage, built.group), run_time={max(0.8, beat_time * 2)})")
            write("        # `stage` keeps the identity Transform mutated in place")
            write("        for motion in built.motions:")
            write(f"            self.play(motion(), run_time={max(1.0, round(scene.seconds / 3, 2))})")
        elif scene.component:
            write("        if stage is not None:")
            write("            self.play(FadeOut(stage), run_time=0.4)")
            write(f"        built = build({scene.component!r}, {scene.parameters!r})")
            write("        place(built.group, regions['stage'])")
            lines.extend(_nudge("built.group", scene.overrides))
            write("        stage = built.group")

            # Components declare their own reveal order. Reading it at runtime
            # keeps the emitted scene correct when a component's beats change.
            write("        for beat in built.beats:")
            write("            parts = [built.parts[name] for name in beat if name in built.parts]")
            write("            if parts:")
            # Drawn, not faded in. A curve traced from one end reads as a curve
            # being drawn; the same curve at full opacity reads as a photograph
            # of one, and that was every beat of every component.
            write(f"                self.play(reveal_all(parts, run_time={max(0.8, beat_time)}))")
            write("        if not built.beats:")
            write(f"            self.play(reveal_all([built.group], run_time={max(0.8, beat_time)}))")
            # Whatever the component says happens in it. Beats only reveal, so
            # without this every figure in the library stood still and a
            # question about a ball bouncing got a picture of a ball.
            write("        for motion in built.motions:")
            write(f"            self.play(motion(), run_time={max(1.0, round(scene.seconds / 3, 2))})")
        else:
            # An equation scene needs the stage to itself.
            write("        if stage is not None:")
            write("            self.play(FadeOut(stage), run_time=0.4)")
            write("            stage = None")
        standing = key

        if scene.caption:
            # Without a component the equation is the scene, so it belongs on
            # the stage at full size rather than shrunk into the caption strip.
            region, size = ("caption", 30) if scene.component else ("stage", 44)
            # A caption is either an equation or a sentence, and they need
            # different mobjects. MathTex sets an English sentence in italic
            # maths with the spaces stripped out — unreadable when it compiles,
            # and a LaTeX error when it does not, which is how a caption about
            # a projectile took a render down. Text has no LaTeX to fail in and
            # renders Unicode natively, so prose goes there untouched — and so
            # does maths threaded with prose, and maths carrying a character
            # nobody has a LaTeX spelling for: a deck about weight matrices
            # lost four clips at once to captions that were maths by every
            # marker and undigestible by TeX.
            if (
                looks_like_maths(scene.caption)
                and not mixes_prose(scene.caption)
                and not unsupported(scene.caption)
            ):
                write(f"        caption = MathTex({to_latex(scene.caption)!r}, font_size={size})")
            else:
                write(f"        caption = Text({scene.caption!r}, font_size={min(size, 30)})")
                write("        caption.scale_to_fit_width(min(caption.width, regions['caption'].width))")
            lines.extend(_nudge("caption", scene.overrides))
            if scene.bridge_text:
                write(f"        bridge = Text({scene.bridge_text!r}, font_size=22, color=GREY_B)")
            # The carried equation, the bridge and the new line are stacked and
            # placed as one group. Positioning them separately and nudging by
            # hand put "halve the width again" straight across the equation it
            # was carrying — three things arranged into one strip, each
            # correctly placed and collectively unreadable. Arranging first
            # lets `place` scale the lot to fit whatever is there.
            if read_equation:
                # A carried equation is already sitting in this region, so it
                # is shrunk and lifted to make room rather than being arranged
                # with the new line — the strip below only works when the
                # region is empty.
                write(f"        place(caption, regions[{region!r}])")
                write("        if equation_memory is not None:")
                write("            self.play(equation_memory.animate.scale(0.72).shift(UP * 0.28), run_time=0.35)")
                write("            caption.shift(DOWN * 0.22)")
                if scene.bridge_text:
                    write("        bridge.next_to(caption, UP, buff=0.1)")
            elif scene.bridge_text:
                # Nothing carried, so the bridge and the line are arranged as
                # one block and placed together. Positioning them separately
                # and nudging by hand put the bridge across the line it
                # introduced.
                write("        strip = VGroup(bridge, caption)")
                write("        strip.arrange(DOWN, buff=0.12)")
                write(f"        place(strip, regions[{region!r}])")
            else:
                write(f"        place(caption, regions[{region!r}])")
            if scene.bridge_text:
                write("        self.play(FadeIn(bridge, shift=UP * 0.06), run_time=0.3)")
                write("        chrome.append(bridge)")
            write(f"        self.play(Write(caption), run_time={max(0.6, beat_time)})")
            write("        chrome.append(caption)")
            write("        equation_memory = caption")

        # Hold to the slide's declared length: whatever the animations took,
        # the scene stays up until `seconds` have passed, with a breath at
        # minimum. This is what lets narration own a slide's duration.
        write(
            f"        self.wait(max(0.4, {round(scene.seconds, 2)}"
            " - (self.renderer.time - scene_started)))"
        )
        if "equation" in scene.forget_after:
            write("        if equation_memory is not None:")
            write("            self.play(FadeOut(equation_memory), run_time=0.3)")
            write("            chrome = [m for m in chrome if m is not equation_memory]")
            write("            equation_memory = None")
        if "diagram" in scene.forget_after:
            write("        if stage is not None:")
            write("            self.play(FadeOut(stage), run_time=0.3)")
            write("            stage = None")
        write("")

    write("        leaving = chrome + ([stage] if stage is not None else [])")
    write("        if leaving:")
    write("            self.play(*[FadeOut(m) for m in leaving], run_time=0.5)")

    return _header(style) + "\n".join(lines) + "\n"


def estimated_seconds(plan: ScenePlan) -> float:
    """Roughly what the assembled scene runs to."""
    return round(sum(a.seconds for a in plan.assignments), 1)
