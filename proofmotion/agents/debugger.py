"""Repair a scene that failed to render.

The agent this replaces was handed a traceback and nothing else, so its fix was
another guess at the same 2,837-way choice. This one gets the same lookup tools
that wrote the code, and the validator's report naming the valid alternatives.
"""

from __future__ import annotations

import json
import ast
from typing import Any

from proofmotion.agents.coder import _strip_fences, ensure_bright_background
from proofmotion.runtime.loop import run_agent
from proofmotion.tools import toolset
from proofmotion.tools.manim_api import manim_validate_code

SYSTEM = """You repair Manim scenes that failed to render.

Work out what the error actually says before changing anything. Then confirm the
real API with manim_signature or manim_members — most render failures are a
keyword argument or method that does not exist, and the fix is a lookup, not a
guess.

Run manim_validate_code on your repaired source before returning it.

Change what is broken and leave the rest alone. Keep the single GeneratedScene
class and every equation from the original: the mathematics was verified, so a
"fix" that alters it is a regression.

If the error says the scene is incomplete or produced only a still image,
complete the scene with real self.play(...) animation beats. `self.add(...)`
alone is not a video. Preserve the existing objects and equations, animate them
into view, and include a readable final answer beat.

If the failure says the scene is not grounded in the verified result, the
current source answered the wrong problem. Replace unrelated mathematics with
the required verified equations named in the failure. Do not preserve irrelevant
expressions just because they appear in the broken source.

Return the complete corrected Python source and nothing else."""

COMPACT_SOURCE_RULE = """
The animation may be as long as necessary, but keep the repaired source under
350 lines. Use helpers, data lists, and loops for repeated teaching beats. Never
return an incomplete file because the response ran out of space.
"""


def _usable_source(code: str) -> bool:
    if not code.strip() or "GeneratedScene" not in code:
        return False
    try:
        ast.parse(code)
    except SyntaxError:
        return False
    return True


POLISH_SYSTEM = """You fix layout defects in a Manim scene that already runs.

You are given a measurement of what the scene actually puts on screen, beat by
beat. It is not an opinion; the boxes were measured from your own code.

The usual causes, in order of how often they are the answer:
  - Something from an earlier section was never removed, so the new content is
    drawn on top of it. Fade out or remove what a beat has finished with.
  - Two things are placed in the same region. Put them on separate rows, or
    show them one at a time.
  - font_size is too small to read. Raise it, or shorten the text.
  - Something sits past the frame edge. Move it in, or scale the group down.

Re-run inspect_scene after your changes and keep going until it reports ok.

Change layout only. Every equation, value, and animation must survive: the
mathematics was verified, so altering it is a regression, not a fix.

Return the complete corrected Python source and nothing else."""


def polish_scene(client: Any, code: str, report: dict[str, Any], *, max_iterations: int = 8) -> dict[str, Any]:
    """Fix measured layout defects in a scene that renders but reads badly."""
    summary = json.dumps(
        {
            "text_overlaps": report.get("text_overlaps", [])[:12],
            "out_of_frame": report.get("out_of_frame", [])[:12],
            "unreadable_text": report.get("unreadable_text", [])[:12],
            "advice": report.get("advice", ""),
        },
        indent=2,
    )
    result = run_agent(
        client,
        POLISH_SYSTEM,
        f"Measured layout problems in this scene:\n{summary}\n\nCURRENT SOURCE:\n{code}",
        toolset("manim", "visual"),
        max_iterations=max_iterations,
        max_tokens=8000,
        agent_name="polisher",
        final_instruction=(
            "Stop calling tools. Output the complete corrected Manim source now: "
            "from manim import * followed by one GeneratedScene class. Code only."
        ),
    )
    fixed = _strip_fences(result.content)
    return {"code": fixed, "tools_used": result.tools_used}


def repair_scene(client: Any, code: str, error: str, *, max_iterations: int = 10) -> dict[str, Any]:
    """Attempt a repair, returning the new source and its validation report."""
    report = manim_validate_code(code)
    static = (
        "\n\nStatic validation of the current code reports:\n"
        + "\n".join(
            f"  line {p.get('line')}: {p.get('call', '')} {p['problem']}"
            + (f"  (valid: {', '.join(p.get('did_you_mean') or p.get('valid', [])[:8])})" if p.get("valid") or p.get("did_you_mean") else "")
            for p in report["problems"]
        )
        if report["problems"]
        else ""
    )
    result = run_agent(
        client,
        SYSTEM + COMPACT_SOURCE_RULE,
        f"This scene failed to render.\n\nRENDER ERROR:\n{error[-3000:]}{static}\n\nCURRENT SOURCE:\n{code}",
        toolset("manim", "visual"),
        max_iterations=max_iterations,
        max_tokens=10000,
        agent_name="debugger",
    )
    fixed = _strip_fences(result.content)
    if not _usable_source(fixed):
        # A short direct request avoids returning an empty/prose reply after a
        # repair agent used all of its API lookup turns.
        direct = client.complete(
            SYSTEM
            + COMPACT_SOURCE_RULE
            + "\n\nTool use is unavailable. Output the entire corrected source now, including "
            "self.play(...) animation beats. Keep it compact and complete. Code only.",
            f"Failure: {error[-2000:]}\n\nCURRENT SOURCE:\n{code}",
            max_tokens=16000,
        )
        fixed = _strip_fences(direct or "")
    fixed = ensure_bright_background(fixed)
    return {
        "code": fixed,
        "validation": manim_validate_code(fixed) if fixed else {"valid": False, "problems": []},
        "tools_used": result.tools_used,
    }
