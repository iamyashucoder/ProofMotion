"""Understand what the user actually asked for.

Replaces a chain of `if "gradient descent" in prompt` branches that recognised
three topics and sent everything else to a one-scene stub.
"""

from __future__ import annotations

from typing import Any

from proofmotion.runtime.loop import run_structured
from proofmotion.tools import toolset
from schemas.intent import AnimationIntent

SYSTEM = """You work out what a mathematical or scientific animation request is really asking for.

Decide the topic, the field it belongs to, who it is for, and what the viewer
should understand afterwards. Judge honestly whether it needs a graph, a
derivation, a numerical simulation, or three dimensions.

You have symbolic and numerical tools. Use them when the request names a
specific function or claim and you need to know what you are dealing with.

Any topic is in scope, from arithmetic to research mathematics and physics. If
the request is vague, choose one concrete example that makes it teachable and
record that choice in `assumptions`.

For JEE Advanced, JEE Main, NEET, Olympiad, or other competitive-exam prompts,
call competitive_exam_requirements first. Its required solution structure is a
contract: preserve all given quantities, demand a labelled diagram where the
question has a physical or geometric setup, and do not skip algebraic steps.

Keep duration_seconds short unless the request asks otherwise. Around 30 seconds
suits most explanations and 45 is generous; a viewer learns more from a tight
explanation than a thorough one. Only go beyond 45 when the request explicitly
asks for depth or names several things to cover."""


def understand_request(
    client: Any, user_prompt: str, *, images: list[str] | None = None
) -> AnimationIntent:
    """Turn a free-form request into a structured intent.

    `images` are what the person attached — a photographed problem is the
    request, so reading it here is reading the request.
    """
    return run_structured(
        client,
        SYSTEM,
        f"Animation request:\n{user_prompt}",
        toolset("compute", "competitive"),
        AnimationIntent,
        max_iterations=6,
        agent_name="intent",
        images=images,
    )
