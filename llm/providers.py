"""Provider-agnostic LLM access.

ProofMotion is not tied to a model vendor (see PLAN.md §0). Every provider here
speaks the OpenAI chat-completions wire format, so a single implementation
covers OpenRouter, DeepSeek, and a local vLLM server on the A6000s.

Select a provider with PROOFMOTION_LLM_PROVIDER, or call get_client("deepseek").
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
log = logging.getLogger(__name__)


class LLMError(RuntimeError):
    """A configured provider failed.

    Deliberately raised rather than swallowed. Returning None on an API error
    would silently degrade the pipeline to template output and hide the cause.
    None is reserved for "this provider is not configured".
    """


@dataclass
class Completion:
    """A response, plus the reasoning trace when the model exposes one.

    The trace matters later: the Phase 3 proof kernel scores candidate steps,
    and how a model reached a step is evidence about whether to expand it.
    """

    content: str
    reasoning: str | None = None
    model: str = ""
    usage: dict[str, Any] = field(default_factory=dict)


class OpenAICompatibleClient:
    """One client for any endpoint speaking OpenAI chat-completions."""

    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        extra_body: dict[str, Any] | None = None,
        temperature: float = 0.2,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.extra_body = extra_body or {}
        self.temperature = temperature
        self.timeout = timeout

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4000,
    ) -> Any:
        """One raw turn, returning the assistant message.

        The message may carry tool_calls instead of content; the agent loop owns
        that decision, so this deliberately returns the message rather than text.
        """
        if not self.available:
            raise LLMError(f"{self.name} has no API key configured")
        # Free/pooled tiers intermittently return an empty choices list. That is
        # transient routing, not a bad request, so a couple of retries are honest.
        for attempt in range(3):
            try:
                response = self._client().chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=max_tokens,
                    extra_body=self.extra_body or None,
                    **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                )
            except Exception as error:
                log.error("%s chat failed (model=%s): %s", self.name, self.model, error)
                raise LLMError(f"{self.name} chat failed (model={self.model}): {error}") from error
            if response.choices:
                return response.choices[0].message
            log.warning("%s returned no choices (attempt %s/3, model=%s)", self.name, attempt + 1, self.model)
        raise LLMError(f"{self.name} returned no choices after 3 attempts (model={self.model})")

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 4000) -> str | None:
        """Satisfies the llm.base_client.LLMClient protocol."""
        result = self.complete_full(system_prompt, user_prompt, max_tokens=max_tokens)
        return result.content if result else None

    def complete_full(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 4000) -> Completion | None:
        if not self.available:
            return None
        try:
            response = self._client().chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                max_tokens=max_tokens,
                extra_body=self.extra_body or None,
            )
        except Exception as error:
            log.error("%s request failed (model=%s): %s", self.name, self.model, error)
            raise LLMError(f"{self.name} request failed (model={self.model}): {error}") from error

        if not response.choices:
            raise LLMError(f"{self.name} returned no choices (model={self.model})")

        message = response.choices[0].message
        return Completion(
            content=message.content or "",
            # Reasoning models expose the trace under a non-standard field.
            reasoning=getattr(message, "reasoning_content", None) or getattr(message, "reasoning", None),
            model=response.model or self.model,
            usage=response.usage.model_dump() if response.usage else {},
        )


def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() not in {"0", "false", "no", "off", ""}


class DeepSeekClient(OpenAICompatibleClient):
    """DeepSeek, including its extended thinking controls.

    Mirrors:
        curl https://api.deepseek.com/chat/completions \\
          -H "Authorization: Bearer $DEEPSEEK_API_KEY" \\
          -d '{"model": "...", "thinking": {"type": "enabled"},
               "reasoning_effort": "high", ...}'

    `thinking` and `reasoning_effort` are not in the OpenAI schema, so they go
    through extra_body, which the SDK merges into the request JSON verbatim.
    """

    name = "deepseek"
    DEFAULT_MODEL = "deepseek-v4-pro"

    def __init__(
        self,
        model: str | None = None,
        *,
        thinking: bool | None = None,
        reasoning_effort: str | None = None,
        **kwargs: Any,
    ) -> None:
        extra: dict[str, Any] = {}
        want_thinking = _flag("DEEPSEEK_THINKING") if thinking is None else thinking
        if want_thinking:
            # reasoning_effort only tunes an enabled thinking budget, so the two
            # travel together rather than leaking an orphaned knob into the request.
            extra["thinking"] = {"type": "enabled"}
            effort = reasoning_effort or os.getenv("DEEPSEEK_REASONING_EFFORT", "high")
            if effort:
                extra["reasoning_effort"] = effort
        super().__init__(
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            api_key=os.getenv("DEEPSEEK_API_KEY"),
            model=model or os.getenv("DEEPSEEK_MODEL", self.DEFAULT_MODEL),
            extra_body=extra,
            **kwargs,
        )


class OpenRouterClient(OpenAICompatibleClient):
    name = "openrouter"
    # Free tier, 262k context, and verified to support tool calling — which the
    # agent loop depends on. Free-tier rate limits (429) apply.
    DEFAULT_MODEL = "google/gemma-4-26b-a4b-it:free"

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
            model=model or os.getenv("OPENROUTER_MODEL", self.DEFAULT_MODEL),
            **kwargs,
        )


class LocalVLLMClient(OpenAICompatibleClient):
    """A vLLM server on this host's A6000s. Auth is a placeholder vLLM ignores."""

    name = "vllm"

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=os.getenv("VLLM_BASE_URL", "http://127.0.0.1:8000/v1"),
            api_key=os.getenv("VLLM_API_KEY", "EMPTY"),
            model=model or os.getenv("VLLM_MODEL", ""),
            **kwargs,
        )


PROVIDERS: dict[str, type[OpenAICompatibleClient]] = {
    "deepseek": DeepSeekClient,
    "openrouter": OpenRouterClient,
    "vllm": LocalVLLMClient,
}


def get_client(provider: str | None = None, model: str | None = None) -> OpenAICompatibleClient | None:
    """Return a configured client, or None when the provider has no credentials.

    None means "run the deterministic path". A misconfigured provider name is a
    mistake, not a fallback, so it raises.
    """
    provider = (provider or os.getenv("PROOFMOTION_LLM_PROVIDER", "openrouter")).strip().lower()
    if provider not in PROVIDERS:
        raise LLMError(f"Unknown provider {provider!r}. Available: {', '.join(sorted(PROVIDERS))}")
    client = PROVIDERS[provider](model)
    if not client.available:
        log.warning("Provider %r has no API key; deterministic path will be used.", provider)
        return None
    return client
