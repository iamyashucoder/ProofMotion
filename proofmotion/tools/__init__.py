"""Fundamental tools available to ProofMotion agents.

Importing this package registers every tool. Nothing here encodes a topic:
there is no gradient-descent tool, only differentiation, iteration, and
measurement, which compose into gradient descent and into everything else.
"""

from proofmotion.runtime.registry import REGISTRY
from proofmotion.tools import (
    algebra,
    analysis,
    components_tool,
    competitive,
    discrete,
    geometry,
    inspect_scene,
    layout,
    learned_tool,
    manim_api,
    numeric,
    reasoning,
    statistics,
    symbolic,
    typeset,
)

#: Referenced so the imports are genuinely used. Registration happens as an
#: import side effect, and `ruff --fix` once deleted components_tool as unused —
#: silently unregistering component_search and component_build, which then failed
#: only at runtime inside an agent. A tuple a linter can see cannot be pruned.
_REGISTERING_MODULES = (
    algebra, analysis, components_tool, competitive, discrete, geometry, inspect_scene,
    layout, learned_tool, manim_api, numeric, reasoning, statistics, symbolic,
    typeset,
)

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
        "symbolic_algebra",
        "symbolic_matrix",
        "symbolic_vector_calculus",
        "symbolic_ode",
        "numeric_ode",
        "numeric_optimize",
        "numeric_interpolate",
    ],
    #: Discrete structures, counting, and exact integer arithmetic.
    "discrete": ["number_theory", "combinatorics", "logic_table", "graph_algorithm"],
    #: Chance and data.
    "stats": ["probability", "statistics_summary", "linear_regression", "monte_carlo"],
    #: Analytic geometry.
    "geometry": ["geometry_solve", "conic_properties"],
    "competitive": [
        "competitive_exam_requirements",
        "jee_mechanics",
        "stoichiometry_limit",
        "ideal_gas_state",
        "weak_acid_ph",
    ],
    #: Checking that a result is right, as distinct from producing one.
    "verify": [
        "units_check",
        "counterexample_search",
        "limiting_case_check",
        "plausibility_check",
        "assumption_check",
        "induction_check",
        "symmetry_check",
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
        "typeset_scene",
        "inspect_scene",
        "component_search",
        "component_build",
        "component_source",
        "component_learn",
    ],
}


#: Umbrella groups, so an agent asks for a capability rather than a list.
UMBRELLAS: dict[str, tuple[str, ...]] = {
    #: Everything that computes an answer, across every subject.
    "compute": ("math", "discrete", "stats", "geometry"),
    #: Everything that decides whether an answer is right.
    "reason": ("verify",),
}


def toolset(*groups: str):
    """Return a registry containing the named groups, e.g. toolset("manim", "visual")."""
    names: list[str] = []
    for group in groups:
        for resolved in UMBRELLAS.get(group, (group,)):
            if resolved not in TOOLSETS:
                raise KeyError(
                    f"Unknown toolset {resolved!r}. Available: {sorted(TOOLSETS)} "
                    f"or umbrellas {sorted(UMBRELLAS)}"
                )
            names.extend(TOOLSETS[resolved])
    return REGISTRY.subset(dict.fromkeys(names))


__all__ = ["REGISTRY", "TOOLSETS", "toolset"]
