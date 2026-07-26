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

Start with component_search. Components are tested builders that already own the
hard parts — axis ranges derived from the actual function, label positions scored
against the geometry, text fitted to its region. Composing one is both less work
and more reliable than positioning objects yourself, and their layout is verified
before you see it.

    built = build("function_plot", dict(expr="(x-2)**2+1", x_min=-1, x_max=5))
    self.play(Create(built.parts["axes"]))
    self.play(Create(built.parts["curve"]))

`built.parts` holds the named pieces and `built.beats` gives a sensible reveal
order, so you animate the pieces rather than placing them.

Write raw Manim only where no component fits. That is expected for anything
unusual — it is a normal outcome, not a failure — but check first, because a
hand-placed label on a curve is the defect this system exists to remove.

When you do write it yourself, do not write any Manim API call from memory.
Look it up:
  manim_search    — find what exists
  manim_signature — the real parameters, defaults, and docs
  manim_members   — what methods a class has
If you are unsure whether a keyword argument exists, that means you must check it.

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

Use a bright, high-contrast visual palette. Set
`self.camera.background_color = "#1E293B"` at the start of construct, then use
white/light text and vivid accent colours such as YELLOW, TEAL, BLUE, GREEN, or
GOLD. Do not use Manim's default near-black background or low-opacity objects
that disappear into it.

Use layout_measure, layout_frame, and layout_check to place things, then run
inspect_scene on your finished source. inspect_scene executes the scene without
rendering and measures the real bounding boxes beat by beat, so it catches
overlaps that planning missed. Fix everything it reports and run it again. It
is the difference between a layout you intended and the one you wrote.

Non-negotiable ProofMotion visual contract:
  - Keep the original user question visible in a small, high-contrast question
    card in one corner (normally upper-left). Use a concise faithful wrap when
    it is long; never cover the main mathematics with it.
  - Reserve the final beat for a clear heading `FINAL ANSWER` and the verified
    answer below it. The answer must follow from the supplied verified plan;
    do not invent a result to make the ending look complete.
  - Render mathematical notation as MathTex, Tex, or TypstMath, never as plain
    Text. This is especially important for roots, logarithms, fractions,
    powers, vectors, and modular arithmetic. Text is for natural-language
    narration only.
  - When a graph, coordinate axes, vector diagram, geometric construction, or
    other line-based mathematical object is introduced, a small turtle carrying
    a visible marker must draw its main stroke. Construct the turtle from basic
    Manim shapes when no asset is supplied; attach the marker tip to the turtle;
    animate it with MoveAlongPath and leave the ink with TracedPath or an
    equivalent progressive path. The turtle must draw the object, not merely
    sit beside a completed graph.
  - Fit every existing text or maths object to the safe frame before displaying
    it. If width or height exceeds the safe area, scale the existing mobject
    down with scale_to_fit_width/scale_to_fit_height. If that would make it
    unreadable, split it across beats rather than allowing overlap or clipping.
  - When the brief's audience is beginner or difficulty is introductory, show a
    short plain-language Text caption for every new idea (maximum 12 words).
    Define symbols on first use, such as `x: position`, `v: how position
    changes`, and `a: how velocity changes`. Keep captions visible long enough
    to read, then clear them before the next idea. Do not replace explanation
    with a dense chain of algebraic equalities.
  - For beginner scenes, this is an explanation, not an answer reveal. Show
    the setup and intuition first, then definitions, then one justified move
    per beat. Keep `FINAL ANSWER` for the last 15% of the timeline. Use at
    least one explanatory caption for every mathematical-plan step, in
    addition to the persistent question card and final answer heading.

Use however many well-paced animation beats are needed to teach the concept.
Combine only changes that the viewer can understand together; never collapse
important reasoning merely to make the video shorter.

Video duration and source-code size are independent. A long explanation is
welcome, but the source must remain compact and complete: aim for fewer than
350 lines. Use small helper functions, VGroups, and data lists with loops for
repeated equation/caption beats. Never expand a long explanation into hundreds
of nearly identical self.play calls. A complete concise scene is essential;
never return a partial file because the response became too long.

Requirements:
  - exactly one Scene subclass, named GeneratedScene
  - start with: from manim import *
  - animate visible objects with self.play(...). A scene that only uses
    self.add(...) produces a still PNG instead of the requested MP4.
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


def _usable_source(code: str) -> bool:
    """Backward-compatible name for the complete-source predicate."""
    return _usable(code)


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
                "no code fences — Python source only. Keep it under 350 lines by using "
                f"helpers, data lists, and loops. Do not return a partial file.\n\n{brief}"
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


def ensure_bright_background(code: str) -> str:
    """Inject the project background default into otherwise valid scene code."""
    if not _usable(code) or "self.camera.background_color" in code:
        return code
    lines = code.splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith("def construct(self)"):
            indent = line[: len(line) - len(line.lstrip())] + "    "
            lines.insert(index + 1, f'{indent}self.camera.background_color = "#1E293B"')
            return "\n".join(lines) + ("\n" if code.endswith("\n") else "")
    return code


def write_scene(client: Any, context: dict[str, Any], *, max_iterations: int = 8) -> dict[str, Any]:
    """Generate a validated Manim scene.

    Returns the source plus the validation report, so the caller can see whether
    the agent actually converged rather than assuming it did.
    """
    brief = json.dumps(
        {
            "user_question": context.get("user_prompt"),
            "intent": context.get("intent"),
            "verified_plan": context.get("math_plan"),
            "storyboard": context.get("storyboard"),
            "computed_values": context.get("tool_results"),
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
        max_tokens=10000,
        agent_name="coder",
        # A coder that runs out of iterations must still emit code. The generic
        # "answer now" produced an empty response, which then sailed through
        # ast.parse (the empty string is valid Python) and rendered nothing.
        final_instruction=(
            "Stop calling tools. Output the complete Manim source now, exactly as it should "
            "be saved: from manim import * followed by one GeneratedScene class. Keep it compact "
            "with helpers and loops, under 350 lines. Code only."
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
    code = ensure_bright_background(code)
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
