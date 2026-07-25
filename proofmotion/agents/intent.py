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

Keep duration_seconds short unless the request asks otherwise. Around 30 seconds
suits most explanations and 45 is generous; a viewer learns more from a tight
explanation than a thorough one. Only go beyond 45 when the request explicitly
asks for depth or names several things to cover."""


def understand_request(client: Any, user_prompt: str) -> AnimationIntent:
    """Turn a free-form request into a structured intent."""
    return run_structured(
        client,
        SYSTEM,
        f"Animation request:\n{user_prompt}",
        toolset("math"),
        AnimationIntent,
        max_iterations=6,
        agent_name="intent",
    )
