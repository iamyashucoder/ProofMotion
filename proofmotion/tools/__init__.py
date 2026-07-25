"""Fundamental tools available to ProofMotion agents.

Importing this package registers every tool. Nothing here encodes a topic:
there is no gradient-descent tool, only differentiation, iteration, and
measurement, which compose into gradient descent and into everything else.
"""

from proofmotion.runtime.registry import REGISTRY
from proofmotion.tools import layout, manim_api, numeric, symbolic, typeset  # noqa: F401  (import registers)

#: Tools grouped by the job they serve, so an agent is handed only what it needs.
TOOLSETS: dict[str, list[str]] = {
    "math": [
        "symbolic_differentiate",
        "symbolic_integrate",
        "symbolic_simplify",
        "symbolic_solve",
        "symbolic_limit",
        "symbolic_series",
        "symbolic_verify_equality",
        "numeric_evaluate",
        "numeric_sample",
        "numeric_iterate",
        "numeric_roots",
    ],
    "manim": [
        "manim_search",
        "manim_signature",
        "manim_members",
        "manim_validate_code",
    ],
    "visual": [
        "layout_frame",
        "layout_measure",
        "layout_check",
        "typeset_check",
    ],
}


def toolset(*groups: str):
    """Return a registry containing the named groups, e.g. toolset("manim", "visual")."""
    names: list[str] = []
    for group in groups:
        if group not in TOOLSETS:
            raise KeyError(f"Unknown toolset {group!r}. Available: {sorted(TOOLSETS)}")
        names.extend(TOOLSETS[group])
    return REGISTRY.subset(dict.fromkeys(names))


__all__ = ["REGISTRY", "TOOLSETS", "toolset"]
