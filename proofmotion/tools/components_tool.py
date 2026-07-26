"""Component discovery and verified construction.

`component_build` does not just report success — it builds the thing and checks
it. The model gets back a collision count from the real geometry, so "this
composed cleanly" is measured rather than assumed.
"""

from __future__ import annotations

from typing import Any

from proofmotion.components import COMPONENTS, build
from proofmotion.layout.collision import bounds, major_collisions, text_on_ink
from proofmotion.runtime.registry import tool


@tool
def component_search(query: str = "", domain: str = "") -> dict[str, Any]:
    """Find verified components that could express a visual idea.

    Always call this before writing Manim code by hand. A component owns its axis
    ranges, label placement, and text fitting, and is tested not to overlap — so
    composing one is both less work and more reliable than positioning objects
    yourself.

    Args:
        query: Words describing the idea, e.g. "tangent", "area under curve".
        domain: Optional filter, e.g. "calculus", "optimization".
    """
    words = [w for w in query.lower().split() if w]
    matches = []
    for spec in COMPONENTS.values():
        if domain and spec.domain != domain:
            continue
        haystack = f"{spec.name} {spec.summary} {spec.domain}".lower()
        score = sum(1 for w in words if w in haystack)
        if score or not words:
            matches.append((score, spec))
    matches.sort(key=lambda pair: -pair[0])
    found = []
    for _, spec in matches[:8]:
        described = spec.describe()
        if getattr(spec, "learned", False):
            # Say so. A learned component passed admission on one example; a
            # built-in one is tested at its parameter extremes, and a model
            # choosing between them should know which is which.
            described["learned"] = True
            described["rewritten_from"] = getattr(spec, "parent", None)
        found.append(described)
    return {
        "query": query,
        "components": found,
        "note": (
            "Call component_build with a name and parameters. If one is close but not right, "
            "component_source shows how it works and component_learn keeps your rewrite for "
            "future questions. Write raw Manim only if nothing fits."
        ),
    }


@tool
def component_build(name: str, parameters: dict) -> dict[str, Any]:
    """Build a component and verify the geometry it produces.

    Returns the call to place in the scene, plus a measured collision report.
    A non-zero collision count means the parameters are the problem — usually a
    range that crowds the labels — not that the component is broken.

    Args:
        name: Component name from component_search.
        parameters: Parameter object for that component.
    """
    from manim import config, tempconfig

    with tempconfig({"dry_run": True, "disable_caching": True}):
        built = build(name, parameters)
        roots = [built.group]
        collisions = text_on_ink(roots)
        serious = major_collisions(roots)
        left, right, bottom, top = bounds(built.group)
        half_w, half_h = float(config.frame_width) / 2, float(config.frame_height) / 2
        escapes = [
            side
            for side, bad in (
                ("left", left < -half_w), ("right", right > half_w),
                ("bottom", bottom < -half_h), ("top", top > half_h),
            )
            if bad
        ]

    argument_text = ", ".join(f"{key}={value!r}" for key, value in parameters.items())
    return {
        "ok": not serious and not escapes,
        "component": name,
        "parts": sorted(built.parts),
        "beats": built.beats,
        "notes": built.notes,
        "text_on_ink": collisions,
        "out_of_frame": escapes,
        "usage": (
            f"from proofmotion.components import build\n"
            f'built = build("{name}", dict({argument_text}))\n'
            f"# built.group is a VGroup; built.parts holds the pieces; built.beats is the reveal order"
        ),
    }
