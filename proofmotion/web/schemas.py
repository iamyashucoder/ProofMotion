"""Component parameter metadata, computed once per process.

Every component already declares this — types, bounds, and the exact set of
valid options. The page's controls are derived from it rather than written per
component, which is why a slider knows it may not leave the range.

Cached because the registry only changes at import time and when learned
components load, both of which happen before serving starts — and recomputing
fifty-odd JSON schemas on every state fetch was a measurable tax on every
keystroke-driven parameter change.
"""

from __future__ import annotations

from functools import cache
from typing import Any


@cache
def schemas() -> dict[str, dict[str, Any]]:
    from proofmotion.components import COMPONENTS

    out: dict[str, dict[str, Any]] = {}
    for name, spec in COMPONENTS.items():
        schema = spec.params.model_json_schema()
        defs = schema.get("$defs", {})
        fields = {}
        for field, prop in (schema.get("properties") or {}).items():
            resolved = dict(prop)
            ref = (prop.get("allOf") or [{}])[0].get("$ref") or prop.get("$ref")
            if ref:
                resolved.update(defs.get(ref.rsplit("/", 1)[-1], {}))
            fields[field] = resolved
        out[name] = fields
    return out
