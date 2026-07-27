"""Provider-agnostic LLM access.

ProofMotion is not tied to a model vendor (see PLAN.md §0). Every provider here
speaks the OpenAI chat-completions wire format, so a single implementation
covers OpenRouter, DeepSeek, and a local vLLM server on the A6000s.

Select a provider with PROOFMOTION_LLM_PROVIDER, or call get_client("deepseek").
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Any, ClassVar

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
    #: OpenAI's newer models reject max_tokens and require max_completion_tokens,
    #: while DeepSeek and OpenRouter still expect max_tokens. Providers differ, so
    #: the name is a class attribute rather than a hardcoded key.
    token_param = "max_tokens"

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str | None,
        model: str,
        extra_body: dict[str, Any] | None = None,
        temperature: float = 0.0,
        timeout: float = 300.0,
    ) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.model = model
        self.extra_body = extra_body or {}
        self.temperature = temperature
        self.timeout = timeout
        #: Parameters this model has already rejected, learned at runtime.
        self._unsupported: set[str] = set()
        #: Cumulative token usage, so cost is measured rather than guessed.
        self.usage: dict[str, int] = {"prompt": 0, "completion": 0, "calls": 0}

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def _client(self) -> OpenAI:
        return OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=self.timeout)

    def _create(self, **kwargs: Any) -> Any:
        """Call the endpoint, dropping parameters the model refuses.

        Which parameters a model accepts varies by model and changes over time:
        gpt-5.2 takes `temperature`, gpt-5.6 rejects it, and both reject
        `max_tokens`. A hardcoded table of exceptions would be wrong within a
        release, so unsupported parameters are learned from the 400 and
        remembered for the life of this client.
        """
        for name in self._unsupported:
            kwargs.pop(name, None)
        for _ in range(4):
            try:
                return self._client().chat.completions.create(**kwargs)
            except Exception as error:
                rejected = _unsupported_parameter(str(error))
                if rejected is None or rejected not in kwargs:
                    raise
                log.info("%s does not accept %r; retrying without it", self.model, rejected)
                self._unsupported.add(rejected)
                kwargs.pop(rejected)
        raise LLMError(f"{self.name}: could not find an accepted parameter set for {self.model}")

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
                response = self._create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    extra_body=self.extra_body or None,
                    **{self.token_param: max_tokens},
                    **({"tools": tools, "tool_choice": "auto"} if tools else {}),
                )
            except Exception as error:
                # Logged at debug, not error: some callers recover from this —
                # gpt-5.6 refuses tools here and is retried on the Responses
                # endpoint — and an ERROR line for a handled condition makes the
                # log untrustworthy. Genuine failures surface via the raise.
                if _is_transient_connection_error(error) and attempt < 2:
                    delay = 1.0 * (2**attempt)
                    log.warning(
                        "%s connection failed (attempt %s/3, model=%s); retrying in %.0fs",
                        self.name, attempt + 1, self.model, delay,
                    )
                    time.sleep(delay)
                    continue
                log.debug("%s chat failed (model=%s): %s", self.name, self.model, error)
                raise LLMError(f"{self.name} chat failed (model={self.model}): {error}") from error
            if response.choices:
                self._record_usage(response)
                return response.choices[0].message
            log.warning("%s returned no choices (attempt %s/3, model=%s)", self.name, attempt + 1, self.model)
        raise LLMError(f"{self.name} returned no choices after 3 attempts (model={self.model})")

    def _record_usage(self, response: Any) -> None:
        """Accumulate token counts and publish them for the live view."""
        used = getattr(response, "usage", None)
        if used is None:
            return
        prompt = int(getattr(used, "prompt_tokens", 0) or getattr(used, "input_tokens", 0) or 0)
        completion = int(getattr(used, "completion_tokens", 0) or getattr(used, "output_tokens", 0) or 0)
        self.usage["prompt"] += prompt
        self.usage["completion"] += completion
        self.usage["calls"] += 1
        try:
            from proofmotion.runtime.events import BUS

            BUS.emit("usage", model=self.model, prompt=prompt, completion=completion)
        except ImportError:
            pass

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 4000) -> str | None:
        """Satisfies the llm.base_client.LLMClient protocol."""
        result = self.complete_full(system_prompt, user_prompt, max_tokens=max_tokens)
        return result.content if result else None

    def complete_full(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 4000) -> Completion | None:
        if not self.available:
            return None
        try:
            response = self._create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=self.temperature,
                extra_body=self.extra_body or None,
                **{self.token_param: max_tokens},
            )
        except Exception as error:
            log.debug("%s request failed (model=%s): %s", self.name, self.model, error)
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


#: OpenAI reports both "Unsupported parameter: 'x'" and "Unsupported value: 'x'".
_UNSUPPORTED = re.compile(r"[Uu]nsupported (?:parameter|value)s?: '([^']+)'")


def _is_transient_connection_error(error: Exception) -> bool:
    """Whether retrying can reasonably change the outcome.

    Bad credentials and malformed requests must fail immediately. Transport
    drops, timeouts, and temporary provider outages can succeed on retry.
    """
    message = str(error).lower()
    markers = (
        "connection error", "connection reset", "connect timeout", "read timeout",
        "timed out", "temporarily unavailable", "service unavailable", "bad gateway",
        "gateway timeout", "internal server error", "error code: 500", "error code: 502",
        "error code: 503", "error code: 504",
    )
    return any(marker in message for marker in markers) or error.__class__.__name__ in {
        "APIConnectionError", "APITimeoutError",
    }


def _unsupported_parameter(message: str) -> str | None:
    """The parameter an API rejected, if the error names one."""
    found = _UNSUPPORTED.search(message)
    return found.group(1).split(".")[-1] if found else None


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
        # Off by default: on a full pipeline run extended thinking cost roughly
        # 25 minutes and produced no better layout than the same model without
        # it. Set DEEPSEEK_THINKING=1 to turn it back on.
        want_thinking = _flag("DEEPSEEK_THINKING", "0") if thinking is None else thinking
        if want_thinking:
            # reasoning_effort only tunes an enabled thinking budget, so the two
            # travel together rather than leaking an orphaned knob into the request.
            extra["thinking"] = {"type": "enabled"}
            effort = reasoning_effort or os.getenv("DEEPSEEK_REASONING_EFFORT", "high")
            if effort:
                extra["reasoning_effort"] = effort
        else:
            # Disabling has to be said. Both v4 models reason when the key is
            # absent, so omitting it left thinking on for every run this setting
            # claimed to have turned off — measured on "what is 17*23": 61
            # completion tokens and a 154-character trace with the key omitted,
            # 1 token and no trace with it disabled.
            extra["thinking"] = {"type": "disabled"}
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


class OllamaClient(OpenAICompatibleClient):
    """Models served by a local Ollama daemon, over its OpenAI-compatible port.

    Ollama needs no credentials, so `available` cannot mean "has an API key" —
    it means the daemon answers. That check is a real request rather than an
    assumption, because a stopped daemon and a wrong port both look identical
    until something tries to use them.

    Reasoning models here need room. qwen3.6 spends its whole budget thinking
    and emits the tool call afterwards, so at 300 tokens it returned no call and
    no content while at 4000 it called correctly. Ollama's OpenAI endpoint
    ignores `think` and `reasoning_effort` — both were sent and the trace came
    back the same length — so the budget is the only lever, and MIN_TOKENS is
    it.
    """

    name = "ollama"
    DEFAULT_MODEL = "gemma4:latest"

    #: Floor on the completion budget. A local reasoning model that runs out
    #: mid-thought returns an empty message, which reads downstream as a model
    #: that cannot use tools rather than one that was cut off.
    MIN_TOKENS = 4000

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"),
            # The OpenAI SDK requires a key; Ollama ignores whatever it is sent.
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
            model=model or os.getenv("OLLAMA_MODEL", self.DEFAULT_MODEL),
            **kwargs,
        )

    @property
    def available(self) -> bool:
        """Whether the daemon is actually answering on this port."""
        import urllib.error
        import urllib.request

        root = self.base_url.removesuffix("/v1").rstrip("/")
        try:
            with urllib.request.urlopen(f"{root}/api/tags", timeout=5) as response:
                return response.status == 200
        except (urllib.error.URLError, OSError, ValueError) as error:
            log.warning("Ollama is not answering at %s: %s", root, error)
            return False

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4000,
    ) -> Any:
        return super().chat(messages, tools=tools, max_tokens=max(max_tokens, self.MIN_TOKENS))

    def models(self) -> list[str]:
        """Model tags the daemon has pulled, for choosing one that exists."""
        import json as _json
        import urllib.request

        root = self.base_url.removesuffix("/v1").rstrip("/")
        try:
            with urllib.request.urlopen(f"{root}/api/tags", timeout=10) as response:
                payload = _json.loads(response.read())
        except (OSError, ValueError) as error:
            raise LLMError(f"could not list Ollama models at {root}: {error}") from error
        return sorted(m["name"] for m in payload.get("models", []))


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI directly.

    The gpt-5 family rejects max_tokens outright, so token_param changes here.
    Verified against the live API: gpt-5.2 accepts max_completion_tokens and
    refuses max_tokens with a 400; gpt-4.1 accepts either.
    """

    name = "openai"
    token_param = "max_completion_tokens"
    DEFAULT_MODEL = "gpt-5.6-terra"
    #: Models already found to need the Responses endpoint for tools. Remembered
    #: per model rather than per client, so only the first agent in a run pays
    #: for the discovery instead of every one of them.
    _needs_responses: ClassVar[set[str]] = set()

    def __init__(self, model: str | None = None, **kwargs: Any) -> None:
        super().__init__(
            base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            api_key=os.getenv("OPENAI_API_KEY"),
            model=model or os.getenv("OPENAI_MODEL", self.DEFAULT_MODEL),
            **kwargs,
        )
        self._responses_delegate: Any = None

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4000,
    ) -> Any:
        """Chat-completions, falling back to the Responses API when told to.

        gpt-5.6 refuses function tools on /v1/chat/completions unless reasoning is
        switched off, and says so in the error. Rather than keep a list of which
        models need which endpoint — which would be stale within a release — the
        switch is made when the API asks for it, and remembered.
        """
        if self._responses_delegate is None and tools and self.model in OpenAIClient._needs_responses:
            self._responses_delegate = OpenAIResponsesClient(
                self.model, temperature=self.temperature, timeout=self.timeout
            )
        if self._responses_delegate is not None:
            message = self._responses_delegate.chat(messages, tools=tools, max_tokens=max_tokens)
            # The delegate is a separate client, so its tokens land on its own
            # counter. Without folding them back, every gpt-5.6 run reported
            # zero usage and therefore zero cost.
            for key in ("prompt", "completion", "calls"):
                self.usage[key] = self._responses_delegate.usage[key]
            return message
        try:
            return super().chat(messages, tools=tools, max_tokens=max_tokens)
        except LLMError as error:
            if "/v1/responses" not in str(error):
                raise
            log.info("%s requires the Responses API for tools; switching", self.model)
            OpenAIClient._needs_responses.add(self.model)
            delegate = OpenAIResponsesClient(self.model, temperature=self.temperature, timeout=self.timeout)
            self._responses_delegate = delegate
            return delegate.chat(messages, tools=tools, max_tokens=max_tokens)


PROVIDERS: dict[str, type[OpenAICompatibleClient]] = {
    "deepseek": DeepSeekClient,
    "ollama": OllamaClient,
    "openai": OpenAIClient,
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


@dataclass
class _ToolFunction:
    name: str
    arguments: str


@dataclass
class _ToolCall:
    id: str
    function: _ToolFunction
    type: str = "function"


@dataclass
class _Message:
    """Shaped like a chat-completions message, so the agent loop needs no changes."""

    content: str
    tool_calls: list[_ToolCall] | None = None
    reasoning: str | None = None


class OpenAIResponsesClient(OpenAIClient):
    """OpenAI models that need the Responses API to combine reasoning with tools.

    gpt-5.6 rejects function tools on /v1/chat/completions unless reasoning_effort
    is 'none', which throws away the only reason to choose these models. The
    Responses endpoint runs tools with reasoning intact, so this adapts the
    chat-shaped conversation the agent loop speaks to that endpoint and back.
    """

    name = "openai-responses"
    DEFAULT_MODEL = "gpt-5.6-terra"

    @staticmethod
    def _to_responses_tools(tools: list[dict[str, Any]] | None) -> list[dict[str, Any]] | None:
        """Chat nests the schema under "function"; Responses expects it flat."""
        if not tools:
            return None
        flat = []
        for tool in tools:
            function = tool.get("function", tool)
            flat.append(
                {
                    "type": "function",
                    "name": function["name"],
                    "description": function.get("description", ""),
                    "parameters": function.get("parameters", {}),
                }
            )
        return flat

    @staticmethod
    def _to_responses_input(messages: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """Split off the system prompt and translate the rest into input items."""
        instructions = ""
        items: list[dict[str, Any]] = []
        for message in messages:
            role = message.get("role")
            if role == "system":
                instructions = message.get("content") or ""
            elif role == "tool":
                items.append(
                    {
                        "type": "function_call_output",
                        "call_id": message["tool_call_id"],
                        "output": message.get("content") or "",
                    }
                )
            elif role == "assistant" and message.get("tool_calls"):
                if message.get("content"):
                    items.append({"role": "assistant", "content": message["content"]})
                for call in message["tool_calls"]:
                    items.append(
                        {
                            "type": "function_call",
                            "call_id": call["id"],
                            "name": call["function"]["name"],
                            "arguments": call["function"]["arguments"],
                        }
                    )
            elif message.get("content"):
                items.append({"role": role or "user", "content": message["content"]})
        return instructions, items

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 4000,
    ) -> Any:
        if not self.available:
            raise LLMError(f"{self.name} has no API key configured")
        instructions, items = self._to_responses_input(messages)
        request: dict[str, Any] = {
            "model": self.model,
            "input": items,
            "max_output_tokens": max_tokens,
        }
        if instructions:
            request["instructions"] = instructions
        if tools:
            request["tools"] = self._to_responses_tools(tools)
        try:
            response = self._client().responses.create(**request)
        except Exception as error:
            log.debug("%s responses call failed (model=%s): %s", self.name, self.model, error)
            raise LLMError(f"{self.name} responses call failed (model={self.model}): {error}") from error

        self._record_usage(response)
        text, calls, reasoning = "", [], []
        for item in response.output:
            kind = getattr(item, "type", "")
            if kind == "function_call":
                calls.append(_ToolCall(id=item.call_id, function=_ToolFunction(item.name, item.arguments)))
            elif kind == "message":
                for part in getattr(item, "content", []) or []:
                    text += getattr(part, "text", "") or ""
            elif kind == "reasoning":
                for part in getattr(item, "summary", []) or []:
                    reasoning.append(getattr(part, "text", "") or "")
        return _Message(content=text, tool_calls=calls or None, reasoning="\n".join(reasoning) or None)


PROVIDERS["openai-responses"] = OpenAIResponsesClient
