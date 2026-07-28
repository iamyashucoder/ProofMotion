"""Write the Manim scene, with the API available for lookup instead of recital.

This replaces prompts.py — 47 remembered rules covering roughly 2% of Manim's
2,837 valid (method, parameter) pairs, each rule added only after someone hit
the bug it describes. The agent now looks up what it needs, and its code is
checked against the real API before anything renders.
"""

from __future__ import annotations

import ast
import json
import logging
from typing import Any

from proofmotion.runtime.loop import run_agent
from proofmotion.tools import toolset
from proofmotion.tools.manim_api import manim_validate_code

log = logging.getLogger(__name__)

SYSTEM = """You assemble Manim scenes, preferring verified components to hand-written layout.

Every scene draws something. A viewer should be able to follow this with the
sound off, from the pictures alone — so the figure is the scene and the algebra
annotates it, never the reverse. A screen holding only symbols is a page of a
textbook, and they already have one.

Label what you draw. Put the quantities on the figure — the radius, the angle,
the force, the value at the point — so the picture carries the meaning instead
of pointing at a caption elsewhere. Then check every one of those labels with
inspect_scene, because annotation is exactly where hand-written scenes overlap:
each label is fine on its own and they collide with the geometry and with each
other. Annotate generously, then measure, then fix what it reports.

Start with component_search. It returns the whole catalogue — read past the top
of the ranking, because the component you want is often further down under a
name you would not have searched for. A mass on a spring is spring_mass whatever
the question calls it; a block on a slope is inclined_plane; a lens is
ray_diagram; forces on a body are free_body_diagram.

Components are tested builders that already own the
hard parts — axis ranges derived from the actual function, label positions scored
against the geometry, text fitted to its region. Composing one is both less work
and more reliable than positioning objects yourself, and their layout is verified
before you see it.

    built = build("function_plot", dict(expr="(x-2)**2+1", x_min=-1, x_max=5))
    self.play(Create(built.parts["axes"]))
    self.play(Create(built.parts["curve"]))

`built.parts` holds the named Mobjects. `built.beats` is only their reveal order:
each beat contains *string keys*, not Mobjects. Always resolve a beat through
`built.parts` before animating it, for example:

    for beat in built.beats:
        self.play(*[FadeIn(built.parts[name]) for name in beat])

Never write `FadeIn(name)` or `FadeIn(part)` while iterating over
`built.beats`; that passes a string to Manim and crashes at render time.

Write raw Manim only where no component fits. That is expected for anything
unusual — it is a normal outcome, not a failure — but check first, because a
hand-placed label on a curve is the defect this system exists to remove.

When you do write it yourself, do not write any Manim API call from memory.
Look it up:
  manim_search    — find what exists
  manim_signature — the real parameters, defaults, and docs
  manim_members   — what methods a class has
If you are unsure whether a keyword argument exists, that means you must check it.

For Axes, never put ``label`` inside axis_config, x_axis_config, or
y_axis_config. Those dictionaries configure the axis line and Manim will crash
on that key. Make labels as separate Mobjects with
axes.get_axis_labels(x_label=..., y_label=...).

Use MathTex for every equation, superscript, subscript, or mathematical symbol.
Tex is text mode: never put raw ^ or _ inside Tex("..."). For a sentence that
contains a formula, split it into Text/Tex prose and a separate MathTex object.

Ask for several lookups in one turn rather than one at a time. Independent
lookups run concurrently, so six signatures in a single turn cost about what one
costs, while six separate turns burn six round trips of your iteration budget.

Before you finish, run manim_validate_code on your complete source. It compares
every call against the installed Manim and reports invalid arguments together
with the valid ones. Fix what it reports and validate again. Do not return code
that has not passed.

Clear the stage between sections. The single most common defect in generated
scenes is a title or equation from an earlier section still on screen when the
next one is drawn over it — on the finished video that reads as smeared,
half-legible text rather than as two objects. FadeOut or Transform what a
section has finished with before adding its replacement.

Keep text readable. Use font_size 40 or more for titles, and 28 or more for
equations and body text; axis tick labels may be smaller. Never go below 16 —
that is unreadable in the final video. If something does not fit, shorten the
string or give it its own beat, rather than shrinking it until it does.

Use layout_measure, layout_frame, and layout_check to place things, then run
inspect_scene on your finished source. inspect_scene executes the scene without
rendering and measures the real bounding boxes beat by beat, so it catches
overlaps that planning missed. Fix everything it reports and run it again. It
is the difference between a layout you intended and the one you wrote.

Respect the runtime budget in the brief. Roughly two self.play calls per ten
seconds of target length is the right density; thirty-six of them for a one
minute animation is a slideshow, not an explanation. Combine related changes
into a single play with an AnimationGroup rather than animating each object in
turn, and keep self.wait short — 0.5s after a reveal is usually enough, and a
wait after every single beat is what turns a tight explanation into a long one.

For creator or study-animation briefs, use the supplied creator brief as a
contract. Prefer deliberate continuity: TransformMatchingTex for evolving
notation, ValueTracker plus always_redraw for a quantity that changes
continuously, MoveAlongPath with TracedPath for meaningful physical motion, and
MovingCameraScene only when camera movement makes a local relationship easier
to see. Keep a before-state or reference object when comparison matters. Every
motion needs a named teaching purpose; never add spinning, bouncing, flashing,
or camera movement merely as decoration. This is an independent clarity-first
study style, not an imitation of any creator's visual identity.

For a π (pi) character request, use the pi_character component instead of a
small MathTex label. Reveal its large pi_glyph and face first, then animate the
stretchable arm into scratch_arm_pose when the character is confused: transform
the resting arm, fade in the question marks, and make a small hand-scrubbing
motion. Do not draw 3D axes beside or behind the initial character reveal.
First let π occupy the stage, then move it to one side and draw ThreeDAxes in a
later beat. This order is mandatory when the prompt asks for both π and 3D axes.

Requirements:
  - exactly one Scene subclass, named GeneratedScene
  - start with: from manim import *
  - no filesystem, network, or subprocess use
  - only equations that appear in the verified plan you are given

Return the finished Python source and nothing else: no prose, no code fences."""


#: Tools the agent hands complete source to. When it runs out of iterations and
#: emits nothing, the code it was working on is still sitting in these calls.
CODE_BEARING_TOOLS = ("manim_validate_code", "inspect_scene")


def _usable(code: str) -> bool:
    """Complete, parseable source defining the scene. Anything else is not code."""
    if not code or "GeneratedScene" not in code:
        return False
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


def recover_code(tool_calls: list[dict[str, Any]]) -> str:
    """Salvage the last usable scene from the agent's own tool calls.

    "The coding agent returned no code" was never true. The agent validated and
    inspected real source, then hit its iteration cap and answered with nothing,
    and the run failed holding a scene it had already written. The most recent
    call carrying a parseable GeneratedScene is that scene.
    """
    for call in reversed(tool_calls):
        if call["name"] not in CODE_BEARING_TOOLS:
            continue
        try:
            candidate = json.loads(call["arguments"] or "{}").get("code", "")
        except json.JSONDecodeError:
            continue
        if not candidate or "GeneratedScene" not in candidate:
            continue
        try:
            ast.parse(candidate)
        except SyntaxError:
            continue
        return candidate
    return ""


def _component_name(arguments: str) -> str | None:
    """The component a component_build call asked for, if the arguments parse."""
    try:
        return json.loads(arguments or "{}").get("name")
    except json.JSONDecodeError:
        return None


def _strip_fences(code: str) -> str:
    """Extract Python source from a reply that may also contain prose.

    The naive version only stripped a fence at position 0, so a repair that
    began with an explanation was returned verbatim and failed to parse on a
    stray arrow character. Prefer a fenced block that actually parses.
    """
    text = code.strip()
    candidates: list[str] = []
    if "```" in text:
        # Fenced blocks are the odd-indexed segments of a ```-split.
        parts = text.split("```")
        candidates.extend(part.removeprefix("python").removeprefix("py").strip() for part in parts[1::2])
    candidates.append(text)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            ast.parse(candidate)
        except SyntaxError:
            continue
        if "GeneratedScene" in candidate:
            return candidate
    # Nothing parsed with a scene in it. Return the best-effort block so the
    # caller's validator reports a real diagnosis rather than an empty string.
    return next((c for c in candidates if c), "")


def _write_directly(client: Any, brief: str) -> str:
    """One tool-free attempt at the scene.

    The tool loop is what makes the code good; this is what makes it exist. An
    agent that explores until its budget is gone has still read the brief, and
    asking it plainly for the source costs one call.
    """
    from proofmotion.tools import toolset

    try:
        result = run_agent(
            client,
            SYSTEM,
            (
                "Write the complete Manim scene for this brief now. No tools, no explanation, "
                f"no code fences — Python source only.\n\n{brief}"
            ),
            toolset("manim").subset([]),   # an empty registry: nothing to call
            max_iterations=1,
            max_tokens=16000,
            agent_name="coder-direct",
        )
    except Exception as error:  # noqa: BLE001 - the caller reports "no code" either way
        log.warning("direct coder attempt failed: %s", error)
        return ""
    return _strip_fences(result.content)


def write_scene(client: Any, context: dict[str, Any], *, max_iterations: int = 12) -> dict[str, Any]:
    """Generate a validated Manim scene.

    Returns the source plus the validation report, so the caller can see whether
    the agent actually converged rather than assuming it did.
    """
    target = int((context.get("intent") or {}).get("duration_seconds") or 30)
    brief = json.dumps(
        {
            "intent": context.get("intent"),
            "verified_plan": context.get("math_plan"),
            "storyboard": context.get("storyboard"),
            "computed_values": context.get("tool_results"),
            "budget": {
                "target_seconds": target,
                "max_play_calls": max(6, round(target / 5)),
                "guidance": "Total run_time plus waits should land near target_seconds.",
            },
        },
        indent=2,
        default=str,
    )
    result = run_agent(
        client,
        SYSTEM,
        f"Write the scene for this brief.\n\n{brief}",
        toolset("manim", "visual"),
        max_iterations=max_iterations,
        max_tokens=8000,
        agent_name="coder",
        # A coder that runs out of iterations must still emit code. The generic
        # "answer now" produced an empty response, which then sailed through
        # ast.parse (the empty string is valid Python) and rendered nothing.
        final_instruction=(
            "Stop calling tools. Output the complete Manim source now, exactly as it should "
            "be saved: from manim import * followed by one GeneratedScene class. Code only."
        ),
        # A whole scene does not fit in a tool turn's budget. The last run was cut
        # off mid-AnimationGroup at 3716 characters and failed to parse.
        final_max_tokens=16000,
    )
    code = _strip_fences(result.content)
    recovered = retried = False
    if not _usable(code):
        # Truncation was the case this was written for and the case it missed:
        # a scene cut off mid-call still contains "GeneratedScene", so testing
        # for the class name alone let unparseable source through untouched.
        salvaged = recover_code(result.tool_calls)
        if salvaged:
            code, recovered = salvaged, True

    if not _usable(code):
        # Nothing to salvage. That happens when the agent explores without ever
        # handing code to a tool — one run spent 41 calls and validated nothing,
        # so the whole pipeline failed with "returned no code" while the model
        # had simply never been asked plainly. Ask plainly, once, with no tools.
        log.warning("coder produced nothing usable; retrying once with tools withheld")
        code, retried = _write_directly(client, brief), True

    report = manim_validate_code(code) if code else {"valid": False, "problems": [{"problem": "agent returned no code"}]}
    used = sorted({
        m for call in result.tool_calls if call["name"] == "component_build" and not call["failed"]
        for m in [_component_name(call["arguments"])] if m
    })
    return {
        "code": code,
        "validation": report,
        "components_used": used,
        "recovered_from_tool_calls": recovered,
        "wrote_directly": retried,
        "composed": bool(used) and "build(" in code,
        "tools_used": result.tools_used,
        "iterations": result.iterations,
        "stopped_early": result.stopped_early,
    }
