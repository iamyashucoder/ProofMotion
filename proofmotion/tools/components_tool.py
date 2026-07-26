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

#: How many of the closest matches carry their full parameter schema.
DETAILED = 6


@tool
def component_search(query: str = "", domain: str = "") -> dict[str, Any]:
    """List every verified component, with the ones matching your query first.

    Always call this before writing Manim code by hand. A component owns its axis
    ranges, label placement, and text fitting, and is tested not to overlap — so
    composing one is both less work and more reliable than positioning objects
    yourself.

    The whole catalogue comes back every time. Read it rather than trusting the
    ranking — the query only decides the order.

    Args:
        query: Words describing the idea, e.g. "tangent", "area under curve".
        domain: Optional filter, e.g. "calculus", "optimization".
    """
    # Everything, always. This was a substring match that returned the eight
    # best word overlaps, and it was worse than useless: "simple harmonic
    # oscillator" returned nothing at all while spring_mass sat in the library,
    # "rotating disc angular momentum" returned spring_mass because both
    # contain the letters of "mass", and "ball rolling down a ramp" returned
    # eight components, none of them inclined_plane. Agents saw the noise,
    # concluded correctly that nothing fitted, and wrote text — which is why
    # thirteen physics components had never been used in seventy-one runs.
    #
    # The catalogue is 28 entries and about 600 tokens. At this size retrieval
    # is not a problem worth having; enumerating removes it entirely.
    words = [w for w in query.lower().split() if w]
    matches = []
    for spec in COMPONENTS.values():
        if domain and spec.domain != domain:
            continue
        haystack = f"{spec.name} {spec.summary} {spec.domain}".lower()
        score = sum(1 for w in words if w in haystack)
        matches.append((score, spec.name, spec))
    matches.sort(key=lambda triple: (-triple[0], triple[1]))

    # Full parameter schemas for the closest few, one line for the rest. All 28
    # schemas came to 19kB, which is 5k tokens on a tool the director calls
    # several times a run — enumerating the catalogue must not cost more than
    # the search it replaces.
    found, catalogue = [], []
    for rank, (_, _, spec) in enumerate(matches):
        entry = spec.describe() if rank < DETAILED else {
            "name": spec.name, "domain": spec.domain, "summary": spec.summary,
            "required": sorted(spec.params.model_json_schema().get("required", [])),
        }
        if getattr(spec, "learned", False):
            # Say so. A learned component passed admission on one example; a
            # built-in one is tested at its parameter extremes, and a model
            # choosing between them should know which is which.
            entry["learned"] = True
            entry["rewritten_from"] = getattr(spec, "parent", None)
        if not spec.pictorial:
            entry["draws_no_picture"] = True
        (found if rank < DETAILED else catalogue).append(entry)

    return {
        "query": query,
        "count": len(found) + len(catalogue),
        "components": found,
        "rest_of_catalogue": catalogue,
        "note": (
            "components holds the closest matches with their full parameters; "
            "rest_of_catalogue is everything else, one line each. Read past the top — "
            "the ranking is a word-overlap hint, not a filter, and the component you want "
            "is often further down. component_build reports the full parameters of any of "
            "them. If one is close but not right, component_source shows how it works and "
            "component_learn keeps your rewrite. Write raw Manim only if nothing here fits."
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
