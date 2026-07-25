"""Turn plain Python functions into model-callable tools.

The point of this module is that a tool is written *once*, as an ordinary
typed function with a docstring. Its JSON schema is derived from the signature,
so the description the model sees can never drift from what the code accepts —
which is the failure mode that produced a 47-rule prompt in the first place.
"""

from __future__ import annotations

import inspect
import json
import types
import typing
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Union, get_args, get_origin

JSON_TYPES: dict[Any, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


class ToolError(RuntimeError):
    """A tool was called wrongly, or failed.

    Raised rather than returned so the loop can hand the model a corrective
    message instead of letting a bad result masquerade as a good one.
    """


def _json_schema_for(annotation: Any) -> dict[str, Any]:
    """Map a type annotation onto a JSON-schema fragment."""
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}

    origin = get_origin(annotation)

    # Optional[X] / X | None -> schema for X (optionality is expressed by `required`)
    if origin in (Union, types.UnionType):
        inner = [a for a in get_args(annotation) if a is not type(None)]
        return _json_schema_for(inner[0]) if len(inner) == 1 else {}

    if origin is Literal:
        options = list(get_args(annotation))
        return {"type": JSON_TYPES.get(type(options[0]), "string"), "enum": options}

    if origin in (list, typing.List):  # noqa: UP006 - runtime origin comparison
        args = get_args(annotation)
        return {"type": "array", "items": _json_schema_for(args[0]) if args else {}}

    if origin in (dict, typing.Dict):  # noqa: UP006
        return {"type": "object"}

    return {"type": JSON_TYPES.get(annotation, "string")}


def _parse_docstring(doc: str | None) -> tuple[str, dict[str, str]]:
    """Split a Google-style docstring into a summary and per-argument help.

    Argument help matters: it is the only place the model learns what a
    parameter *means*, as opposed to what type it is.
    """
    if not doc:
        return "", {}
    lines = inspect.cleandoc(doc).splitlines()
    summary: list[str] = []
    params: dict[str, str] = {}
    current: str | None = None
    in_args = False
    for line in lines:
        stripped = line.strip()
        if stripped.rstrip(":").lower() in {"args", "arguments", "parameters"}:
            in_args = True
            continue
        if in_args and stripped.rstrip(":").lower() in {"returns", "raises", "example", "examples", "note"}:
            in_args = False
            continue
        if not in_args:
            if stripped:
                summary.append(stripped)
            continue
        if ":" in stripped and not line.startswith((" " * 8, "\t\t")):
            name, _, text = stripped.partition(":")
            current = name.strip().split()[0] if name.strip() else None
            if current:
                params[current] = text.strip()
        elif current and stripped:
            params[current] += " " + stripped
    return " ".join(summary), params


@dataclass
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    fn: Callable[..., Any]

    def as_openai_schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {"name": self.name, "description": self.description, "parameters": self.parameters},
        }


class ToolRegistry:
    """A named collection of tools, dispatchable by name."""

    def __init__(self, tools: typing.Iterable[Tool] = ()) -> None:
        self._tools: dict[str, Tool] = {t.name: t for t in tools}

    def register(self, fn: Callable[..., Any]) -> Callable[..., Any]:
        """Decorator. Derives name, description, and schema from the function."""
        signature = inspect.signature(fn)
        hints = typing.get_type_hints(fn)
        summary, param_docs = _parse_docstring(fn.__doc__)

        properties: dict[str, Any] = {}
        required: list[str] = []
        for name, param in signature.parameters.items():
            if name == "self" or param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
                continue
            schema = _json_schema_for(hints.get(name, param.annotation))
            if name in param_docs:
                schema["description"] = param_docs[name]
            properties[name] = schema
            if param.default is inspect.Parameter.empty:
                required.append(name)

        self._tools[fn.__name__] = Tool(
            name=fn.__name__,
            description=summary or f"Call {fn.__name__}.",
            parameters={"type": "object", "properties": properties, "required": required},
            fn=fn,
        )
        return fn

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    @property
    def names(self) -> list[str]:
        return sorted(self._tools)

    def subset(self, names: typing.Iterable[str]) -> ToolRegistry:
        """A registry holding only the named tools, for agents that need a few."""
        missing = [n for n in names if n not in self._tools]
        if missing:
            raise ToolError(f"Unknown tools: {missing}. Available: {self.names}")
        return ToolRegistry(self._tools[n] for n in names)

    def schemas(self) -> list[dict[str, Any]]:
        return [t.as_openai_schema() for t in self._tools.values()]

    def dispatch(self, name: str, arguments: str | dict[str, Any]) -> Any:
        """Run a tool. Argument errors are surfaced, never silently defaulted."""
        if name not in self._tools:
            raise ToolError(f"Unknown tool {name!r}. Available: {self.names}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError as error:
                raise ToolError(f"{name}: arguments were not valid JSON: {error}") from error
        if not isinstance(arguments, dict):
            raise ToolError(f"{name}: expected an object of arguments, got {type(arguments).__name__}")
        tool = self._tools[name]
        try:
            inspect.signature(tool.fn).bind(**arguments)
        except TypeError as error:
            raise ToolError(f"{name}: {error}. Schema: {json.dumps(tool.parameters['properties'])}") from error
        return tool.fn(**arguments)


#: Every fundamental tool registers here at import time.
REGISTRY = ToolRegistry()
tool = REGISTRY.register
