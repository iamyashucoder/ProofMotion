"""Fundamental tools available to ProofMotion agents.

Importing this package registers every tool. Nothing here encodes a topic:
there is no gradient-descent tool, only differentiation, iteration, and
measurement, which compose into gradient descent and into everything else.
"""

from proofmotion.runtime.registry import REGISTRY
from proofmotion.tools import (
    components_tool,
    inspect_scene,
    layout,
    manim_api,
    numeric,
    symbolic,
    typeset,
)

#: Referenced so the imports are genuinely used. Registration happens as an
#: import side effect, and `ruff --fix` once deleted components_tool as unused —
#: silently unregistering component_search and component_build, which then failed
#: only at runtime inside an agent. A tuple a linter can see cannot be pruned.
_REGISTERING_MODULES = (components_tool, inspect_scene, layout, manim_api, numeric, symbolic, typeset)

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
        "inspect_scene",
        "component_search",
        "component_build",
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
