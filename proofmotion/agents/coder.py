"""Write the Manim scene, with the API available for lookup instead of recital.

This replaces prompts.py — 47 remembered rules covering roughly 2% of Manim's
2,837 valid (method, parameter) pairs, each rule added only after someone hit
the bug it describes. The agent now looks up what it needs, and its code is
checked against the real API before anything renders.
"""

from __future__ import annotations

import ast
import json
from typing import Any

from proofmotion.runtime.loop import run_agent
from proofmotion.tools import toolset
from proofmotion.tools.manim_api import manim_validate_code

SYSTEM = """You write Manim Community Edition scenes.

Do not write any Manim API call from memory. Look it up:
  manim_search    — find what exists
  manim_signature — the real parameters, defaults, and docs
  manim_members   — what methods a class has
If you are unsure whether a keyword argument exists, that means you must check it.

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

Requirements:
  - exactly one Scene subclass, named GeneratedScene
  - start with: from manim import *
  - no filesystem, network, or subprocess use
  - only equations that appear in the verified plan you are given

Return the finished Python source and nothing else: no prose, no code fences."""


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


def write_scene(client: Any, context: dict[str, Any], *, max_iterations: int = 20) -> dict[str, Any]:
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
    )
    code = _strip_fences(result.content)
    report = manim_validate_code(code) if code else {"valid": False, "problems": [{"problem": "agent returned no code"}]}
    return {
        "code": code,
        "validation": report,
        "tools_used": result.tools_used,
        "iterations": result.iterations,
        "stopped_early": result.stopped_early,
    }
