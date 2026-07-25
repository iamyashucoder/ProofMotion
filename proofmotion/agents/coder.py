"""Write the Manim scene, with the API available for lookup instead of recital.

This replaces prompts.py — 47 remembered rules covering roughly 2% of Manim's
2,837 valid (method, parameter) pairs, each rule added only after someone hit
the bug it describes. The agent now looks up what it needs, and its code is
checked against the real API before anything renders.
"""

from __future__ import annotations

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

Use layout_measure, layout_frame, and layout_check to place things. Text that
overlaps other text is the most common failure in generated scenes, and it comes
from guessing at sizes instead of measuring them.

Requirements:
  - exactly one Scene subclass, named GeneratedScene
  - start with: from manim import *
  - no filesystem, network, or subprocess use
  - only equations that appear in the verified plan you are given

Return the finished Python source and nothing else: no prose, no code fences."""


def _strip_fences(code: str) -> str:
    text = code.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if len(text.split("```")) > 1 else text
        text = text.removeprefix("python").strip()
    return text.strip()


def write_scene(client: Any, context: dict[str, Any], *, max_iterations: int = 20) -> dict[str, Any]:
    """Generate a validated Manim scene.

    Returns the source plus the validation report, so the caller can see whether
    the agent actually converged rather than assuming it did.
    """
    brief = json.dumps(
        {
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
        max_tokens=8000,
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
