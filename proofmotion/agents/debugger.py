"""Repair a scene that failed to render.

The agent this replaces was handed a traceback and nothing else, so its fix was
another guess at the same 2,837-way choice. This one gets the same lookup tools
that wrote the code, and the validator's report naming the valid alternatives.
"""

from __future__ import annotations

import json
from typing import Any

from proofmotion.agents.coder import _strip_fences, _usable
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

Return the complete corrected Python source and nothing else."""


def _direct_repair(client: Any, code: str, error: str) -> str:
    """Ask once without tools when a debugger returns a traceback instead of code."""
    result = run_agent(
        client,
        SYSTEM,
        "Return the complete repaired Python scene now. No tools, no prose, and no code fences. "
        "The previous reply was unusable.\n\n"
        f"RENDER ERROR:\n{error[-2000:]}\n\nCURRENT SOURCE:\n{code}",
        toolset("manim").subset([]),
        max_iterations=1,
        max_tokens=16000,
        agent_name="debugger-direct",
    )
    return _strip_fences(result.content)


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
        SYSTEM,
        f"This scene failed to render.\n\nRENDER ERROR:\n{error[-3000:]}{static}\n\nCURRENT SOURCE:\n{code}",
        toolset("manim", "visual"),
        max_iterations=max_iterations,
        max_tokens=8000,
        agent_name="debugger",
    )
    fixed = _strip_fences(result.content)
    if not _usable(fixed):
        fixed = _direct_repair(client, code, error)
    return {
        "code": fixed,
        "validation": manim_validate_code(fixed) if fixed else {"valid": False, "problems": []},
        "tools_used": result.tools_used,
    }
