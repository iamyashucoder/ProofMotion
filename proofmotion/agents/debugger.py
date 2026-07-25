"""Repair a scene that failed to render.

The agent this replaces was handed a traceback and nothing else, so its fix was
another guess at the same 2,837-way choice. This one gets the same lookup tools
that wrote the code, and the validator's report naming the valid alternatives.
"""

from __future__ import annotations

from typing import Any

from proofmotion.agents.coder import _strip_fences
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


def repair_scene(client: Any, code: str, error: str, *, max_iterations: int = 14) -> dict[str, Any]:
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
    )
    fixed = _strip_fences(result.content)
    return {
        "code": fixed,
        "validation": manim_validate_code(fixed) if fixed else {"valid": False, "problems": []},
        "tools_used": result.tools_used,
    }
