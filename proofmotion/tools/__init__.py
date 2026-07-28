"""Fundamental tools available to ProofMotion agents.

Importing this package registers every tool. Nothing here encodes a topic:
there is no gradient-descent tool, only differentiation, iteration, and
measurement, which compose into gradient descent and into everything else.
"""

from proofmotion.runtime.registry import REGISTRY
from proofmotion.tools import (
    algebra,
    analysis,
    answer_oracle,
    calculus,
    cinematic,
    competitive,
    complex_numbers,
    components_tool,
    coordinate_geometry,
    creator,
    discrete,
    experiments,
    geometry,
    inspect_scene,
    jee_experts,
    layout,
    learned_tool,
    manim_api,
    numeric,
    reasoning,
    statistics,
    symbolic,
    three_d_geometry,
    trigonometry,
    typeset,
)

#: Referenced so the imports are genuinely used. Registration happens as an
#: import side effect, and `ruff --fix` once deleted components_tool as unused —
#: silently unregistering component_search and component_build, which then failed
#: only at runtime inside an agent. A tuple a linter can see cannot be pruned.
_REGISTERING_MODULES = (
    algebra, analysis, answer_oracle, calculus, cinematic, complex_numbers, components_tool, competitive, coordinate_geometry, creator, discrete, experiments, geometry, inspect_scene,
    layout, learned_tool, jee_experts, manim_api, numeric, reasoning, statistics, symbolic, three_d_geometry, trigonometry,
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
        "complex_number_analysis",
        "complex_number_operation",
        "complex_polynomial_roots",
        "roots_of_unity",
        "complex_locus",
        "matrix_arithmetic",
        "matrix_row_operation",
        "matrix_linear_system",
        "matrix_properties",
        "determinant_cofactor_expansion",
        "determinant_row_effect",
        "determinant_parameter_solve",
        "determinant_signed_area",
        "symbolic_vector_calculus",
        "symbolic_ode",
        "numeric_ode",
        "numeric_optimize",
        "numeric_interpolate",
        "calculus_curve_analysis",
        "calculus_limit_continuity",
        "calculus_tangent_normal",
        "calculus_definite_integral",
        "calculus_area_between_curves",
        "calculus_taylor_approximation",
        "calculus_parametric_analysis",
        "calculus_multivariable_analysis",
        "calculus_autonomous_ode",
        "coordinate_line_analysis",
        "coordinate_circle_analysis",
        "coordinate_conic_classify",
        "coordinate_triangle_centres",
        "coordinate_section_formula",
        "coordinate_transform",
        "coordinate_locus_ratio",
        "hyperbola_latus_rectum_right_angle",
        "trig_exact_values",
        "trig_identity_check",
        "trig_equation_solve",
        "trig_inverse_principal",
        "trig_law_of_cosines",
        "trig_law_of_sines",
        "trig_wave_analysis",
    ],
    #: Discrete structures, counting, and exact integer arithmetic.
    "discrete": ["number_theory", "combinatorics", "logic_table", "graph_algorithm"],
    #: Chance and data.
    "stats": ["probability", "statistics_summary", "linear_regression", "monte_carlo"],
    #: Analytic geometry.
    "geometry": ["geometry_solve", "conic_properties"],
    "three_d_geometry": ["three_d_line_plane_intersection", "three_d_line_relation", "three_d_plane_relation", "three_d_point_distance", "three_d_plane_from_points"],
    "competitive": [
        "competitive_exam_requirements",
        "competitive_exam_catalogue",
        "jee_mechanics",
        "meter_scale_alternating_friction",
        "linear_drag_projectile",
        "power_transmission",
        "circuit_network",
        "capacitor_network",
        "electrostatics_point_charges",
        "thermodynamic_process",
        "hydrogen_transition",
        "chemical_equilibrium_direction",
        "ac_phasor_analysis",
        "electromagnetic_induction",
        "wave_optics",
        "fluid_flow_bernoulli",
        "organic_reference_lookup",
        "coordination_complex_analysis",
        "vector_plane_relation",
        "rigid_body_rotation",
        "centre_of_mass",
        "gravitation_orbit",
        "damped_oscillator",
        "terminal_velocity_sphere",
        "radioactive_decay",
        "elasticity_wire",
        "surface_tension_capillary",
        "calorimetry_mix",
        "doppler_effect",
        "ray_optics",
        "photoelectric_effect",
        "semiconductor_diode",
        "heat_conduction",
        "rlc_resonance",
        "polarization_malus",
        "stoichiometry_limit",
        "ideal_gas_state",
        "weak_acid_ph",
    ],
    "creator": ["study_animation_brief", "study_animation_timing", "motion_design_audit"],
    "cinematic": ["cinematic_chase_brief", "vehicle_motion_profile", "non_graphic_action_audit"],
    "experiment": ["measurement_line_fit", "propagate_measurement_uncertainty", "proof_obligations"],
    "jee_experts": ["jee_chapter_expert", "jee_chapter_coverage", "jee_chapter_case"],
    #: Checking that a result is right, as distinct from producing one.
    "verify": [
        "reference_answer_lookup",
        "reference_answer_audit",
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
    "compute": ("math", "discrete", "stats", "geometry", "three_d_geometry"),
    #: Everything that decides whether an answer is right.
    "reason": ("verify",),
    "evidence": ("experiment",),
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
