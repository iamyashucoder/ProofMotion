"""The agent loop: propose, call tools, observe, repeat.

This is what replaces a 47-rule prompt. The system prompt states a goal and
names the tools; everything the agent needs to know about the Manim API, the
mathematics, or the available space is *looked up*, not recited.

A tool error is fed back to the model as an observation rather than raised,
because a wrong call is information the agent can act on. Provider failures
still propagate — those are not something the agent can fix.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from proofmotion.runtime.registry import ToolError, ToolRegistry

log = logging.getLogger(__name__)

MAX_OBSERVATION_CHARS = 6000


@dataclass
class AgentResult:
    content: str
    messages: list[dict[str, Any]] = field(default_factory=list)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    iterations: int = 0
    stopped_early: bool = False

    @property
    def tools_used(self) -> list[str]:
        return [call["name"] for call in self.tool_calls]


def extract_json(text: str) -> Any:
    """Pull a JSON value out of model output, tolerating fences and prose."""
    cleaned = text.strip()
    if "```" in cleaned:
        blocks = [b for b in cleaned.split("```") if b.strip()]
        for block in blocks:
            body = block.removeprefix("json").strip()
            if body.startswith(("{", "[")):
                cleaned = body
                break
    start = min((i for i in (cleaned.find("{"), cleaned.find("[")) if i != -1), default=-1)
    if start == -1:
        raise ValueError(f"no JSON found in model output: {text[:200]!r}")
    for end in range(len(cleaned), start, -1):
        try:
            return json.loads(cleaned[start:end])
        except json.JSONDecodeError:
            continue
    raise ValueError(f"could not parse JSON from: {cleaned[start : start + 200]!r}")


def run_structured(
    client: Any,
    system_prompt: str,
    user_prompt: str,
    registry: ToolRegistry,
    model_cls: Any,
    *,
    max_iterations: int = 10,
    repairs: int = 2,
    # Storyboards and multi-step plans are long documents. The 4000-token
    # default truncates them mid-object, which reads as a parse failure and
    # burns a repair attempt on a problem the model did not have.
    max_tokens: int = 12000,
) -> Any:
    """Run an agent and validate its answer against a Pydantic model.

    A schema violation is handed back with the validation error attached, which
    is a far better repair signal than asking again and hoping.
    """
    schema = json.dumps(model_cls.model_json_schema())
    instruction = f"{user_prompt}\n\nReturn ONLY a JSON object matching this schema:\n{schema}"
    last_error = ""
    for attempt in range(repairs + 1):
        prompt = instruction if not last_error else f"{instruction}\n\nYour previous answer was rejected: {last_error}"
        result = run_agent(client, system_prompt, prompt, registry, max_iterations=max_iterations, max_tokens=max_tokens)
        try:
            return model_cls.model_validate(extract_json(result.content))
        except Exception as error:  # noqa: BLE001 - fed back as a repair signal
            last_error = str(error)[:600]
            log.warning("structured output attempt %s rejected: %s", attempt + 1, last_error)
    raise ToolError(f"{model_cls.__name__} could not be produced after {repairs + 1} attempts. Last error: {last_error}")


def _observation(value: Any) -> str:
    try:
        text = json.dumps(value, default=str)
    except (TypeError, ValueError):
        text = str(value)
    if len(text) > MAX_OBSERVATION_CHARS:
        text = text[:MAX_OBSERVATION_CHARS] + f"... [truncated, {len(text)} chars total]"
    return text


def run_agent(
    client: Any,
    system_prompt: str,
    user_prompt: str,
    registry: ToolRegistry,
    *,
    max_iterations: int = 12,
    max_tokens: int = 4000,
) -> AgentResult:
    """Run a tool-using agent until it answers or runs out of iterations.

    Args:
        client: Any provider from llm.providers.
        system_prompt: The agent's goal. Should describe intent, not API trivia.
        user_prompt: The concrete task.
        registry: Tools this agent may call.
        max_iterations: Cap on model turns, so a confused agent cannot spin.
        max_tokens: Per-turn generation cap.
    """
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    schemas = registry.schemas()
    performed: list[dict[str, Any]] = []

    for iteration in range(1, max_iterations + 1):
        message = client.chat(messages, tools=schemas, max_tokens=max_tokens)
        calls = getattr(message, "tool_calls", None)

        if not calls:
            return AgentResult(
                content=message.content or "",
                messages=messages,
                tool_calls=performed,
                iterations=iteration,
            )

        # Echo the assistant turn back verbatim; providers require tool results
        # to follow the exact call that requested them.
        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": c.id,
                        "type": "function",
                        "function": {"name": c.function.name, "arguments": c.function.arguments},
                    }
                    for c in calls
                ],
            }
        )

        for call in calls:
            name, raw_args = call.function.name, call.function.arguments
            try:
                result = registry.dispatch(name, raw_args)
                observation, failed = _observation(result), False
            except ToolError as error:
                # A misused tool is a correctable observation, not a crash.
                observation, failed = f"ToolError: {error}", True
            except Exception as error:  # noqa: BLE001 - surfaced to the model, and logged
                log.warning("tool %s raised %s: %s", name, type(error).__name__, error)
                observation, failed = f"{type(error).__name__}: {error}", True

            performed.append({"name": name, "arguments": raw_args, "failed": failed})
            messages.append({"role": "tool", "tool_call_id": call.id, "name": name, "content": observation})

    # Out of iterations. Ask once more with no tools offered, so the model must
    # answer from what it has gathered. Returning the last tool result instead
    # would hand the caller raw JSON and call it an answer.
    log.warning("agent hit max_iterations=%s; forcing a final answer", max_iterations)
    messages.append(
        {
            "role": "user",
            "content": "Stop calling tools. Answer now using only what you have already gathered.",
        }
    )
    final = client.chat(messages, tools=None, max_tokens=max_tokens)
    return AgentResult(
        content=final.content or "",
        messages=messages,
        tool_calls=performed,
        iterations=max_iterations,
        stopped_early=True,
    )
