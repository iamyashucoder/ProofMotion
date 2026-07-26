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

Do not choose an arbitrary video length. The downstream planner will use as
many teaching beats as the concept needs."""


def _honour_requested_level(intent: AnimationIntent, user_prompt: str) -> AnimationIntent:
    """A user-specified level outranks a model's guess about the audience."""
    lowered = user_prompt.lower()
    if any(word in lowered for word in ("beginner", "beginners", "beginer", "simple", "easily understand", "easy to understand")):
        intent.audience = "beginner"
        intent.difficulty = "introductory"
    return intent


def understand_request(client: Any, user_prompt: str) -> AnimationIntent:
    """Turn a free-form request into a structured intent."""
    intent = run_structured(
        client,
        SYSTEM,
        f"Animation request:\n{user_prompt}",
        toolset("compute"),
        AnimationIntent,
        max_iterations=6,
        agent_name="intent",
    )
    return _honour_requested_level(intent, user_prompt)
