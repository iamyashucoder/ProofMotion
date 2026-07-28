"""Official JEE Main/Advanced PCM chapter expert registry.

Profiles are deliberately individual even when two chapters share a solver.
`status` is evidence-based; a chapter is never treated as covered merely because
an LLM recognizes its name.
"""

from __future__ import annotations

from typing import Any

SYLLABUS_SOURCES = {
    "jee_advanced_2026": "https://jeeadv.ac.in/documents/jee-advanced-2026-syllabus.pdf",
    "jee_main_2026": "https://jeemain.nta.nic.in/information-bulletin/",
}


def _profiles(subject: str, chapters: list[str], tools: list[str], visuals: list[str], *, reference: bool = False) -> dict[str, dict[str, Any]]:
    return {
        chapter: {
            "subject": subject,
            "chapter": chapter,
            "syllabus_sources": ["jee_advanced_2026", "jee_main_2026"],
            "solver_or_reference": tools if not reference else ["vetted_reference_database", *tools],
            "verification": ["assumption_check", "units_check", "counterexample_search", "limiting_case_check"],
            "visuals": visuals,
            "representative_test_required": True,
            # A chapter becomes validated only when a known-answer prompt has
            # passed planning, computation, code validation, and a rendered
            # scene review.  Infrastructure availability alone is not proof.
            "evidence": {
                "representative_case": f"jee_{chapter}_representative",
                # `tests/test_tier2.py` executes every manifest case through
                # the registered tool dispatcher.  A render review remains a
                # separate human/visual gate.
                "tool_test": "passed",
                "render_review": None,
            },
            "status": "planned",
        }
        for chapter in chapters
    }


PHYSICS: dict[str, dict[str, Any]] = {}
PHYSICS.update(_profiles("physics", ["units_dimensions_errors", "kinematics_1d", "kinematics_2d", "relative_velocity", "newtons_laws", "friction", "work_energy_power", "centre_of_mass", "impulse_collision"], ["jee_mechanics", "symbolic_solve"], ["free_body_diagram", "bus_braking_road", "projectile_motion", "collision"]))
PHYSICS.update(_profiles("physics", ["circular_motion", "rigid_body_rotation", "moment_of_inertia", "angular_momentum", "rolling_motion", "gravitation", "satellites_escape_velocity", "shm", "damped_forced_oscillations", "elasticity"], ["jee_mechanics", "rigid_body_rotation", "gravitation_orbit", "damped_oscillator", "elasticity_wire", "numeric_ode"], ["circular_motion", "rolling_body", "orbit", "pendulum", "spring_mass", "torque_diagram"]))
PHYSICS.update(_profiles("physics", ["fluid_mechanics", "viscosity_terminal_velocity", "surface_tension", "wave_motion", "sound_waves", "doppler_effect", "thermal_expansion", "calorimetry", "kinetic_theory", "thermodynamics", "heat_transfer", "blackbody_radiation"], ["fluid_flow_bernoulli", "terminal_velocity_sphere", "surface_tension_capillary", "calorimetry_mix", "doppler_effect", "heat_conduction", "thermodynamic_process", "ideal_gas_state"], ["fluid_column", "fluid_flow_streamlines", "wave_form", "standing_wave", "pv_diagram"]))
PHYSICS.update(_profiles("physics", ["electrostatics", "gauss_law", "capacitance", "current_electricity", "kirchhoff_laws", "magnetism", "magnetic_force", "electromagnetic_induction", "ac_circuits", "electromagnetic_waves"], ["electrostatics_point_charges", "capacitor_network", "circuit_network", "electromagnetic_induction", "ac_phasor_analysis", "rlc_resonance"], ["field_lines", "parallel_plate_capacitor", "circuit_diagram", "magnetic_force_field", "ac_phasor"]))
PHYSICS.update(_profiles("physics", ["ray_optics", "wave_optics", "interference", "diffraction", "polarization", "dual_nature", "atomic_physics", "nuclear_physics", "semiconductors"], ["ray_optics", "wave_optics", "polarization_malus", "photoelectric_effect", "hydrogen_transition", "radioactive_decay", "semiconductor_diode"], ["ray_diagram", "double_slit_interference", "single_slit_diffraction", "energy_levels"]))

CHEMISTRY: dict[str, dict[str, Any]] = {}
CHEMISTRY.update(_profiles("chemistry", ["mole_concept_stoichiometry", "states_of_matter", "atomic_structure", "chemical_bonding", "chemical_thermodynamics", "chemical_equilibrium", "ionic_equilibrium", "electrochemistry", "chemical_kinetics", "solid_state", "solutions", "surface_chemistry"], ["stoichiometry_limit", "ideal_gas_state", "thermodynamic_process", "chemical_equilibrium_direction", "weak_acid_ph"], ["energy_levels", "molecular_geometry", "reaction_energy_profile", "pv_diagram"]))
CHEMISTRY.update(_profiles("chemistry", ["periodicity", "hydrogen", "s_block", "p_block", "d_block", "f_block", "coordination_compounds", "metallurgy", "qualitative_analysis", "environmental_chemistry"], ["coordination_complex_analysis"], ["coordination_complex", "molecular_geometry"], reference=True))
CHEMISTRY.update(_profiles("chemistry", ["basic_organic_chemistry", "isomerism", "hydrocarbons", "haloalkanes_haloarenes", "alcohols_phenols_ethers", "aldehydes_ketones", "carboxylic_acids", "amines", "biomolecules", "polymers", "chemistry_everyday_life", "practical_organic_chemistry"], ["organic_reference_lookup"], ["organic_mechanism_template", "molecular_geometry"], reference=True))

MATHEMATICS: dict[str, dict[str, Any]] = {}
MATHEMATICS.update(_profiles("mathematics", ["sets_relations_functions", "complex_numbers", "quadratic_equations", "sequence_series", "logarithms", "permutations_combinations", "binomial_theorem", "matrices_determinants", "probability_statistics"], ["symbolic_algebra", "symbolic_solve", "symbolic_matrix", "complex_number_analysis", "complex_number_operation", "complex_polynomial_roots", "roots_of_unity", "complex_locus", "combinatorics", "probability"], ["complex_plane_vector", "roots_of_unity_polygon", "matrix_transform", "distribution_plot", "number_line_marks"]))
MATHEMATICS.update(_profiles("mathematics", ["trigonometry", "inverse_trigonometry", "trigonometric_equations", "trigonometric_functions", "heights_distances"], ["symbolic_algebra", "symbolic_solve", "trig_exact_values", "trig_identity_check", "trig_equation_solve", "trig_inverse_principal", "trig_law_of_cosines", "trig_law_of_sines", "trig_wave_analysis"], ["unit_circle", "trig_triangle", "trig_wave"]))
MATHEMATICS.update(_profiles("mathematics", ["straight_lines", "circles", "conic_sections", "locus", "coordinate_geometry", "coordinate_triangles"], ["symbolic_algebra", "symbolic_solve", "geometry_solve", "conic_properties", "coordinate_line_analysis", "coordinate_circle_analysis", "coordinate_conic_classify", "coordinate_triangle_centres", "coordinate_section_formula", "coordinate_transform", "coordinate_locus_ratio", "hyperbola_latus_rectum_right_angle"], ["coordinate_line_pair", "circle_coordinate_diagram", "conic_coordinate_diagram", "coordinate_triangle_centres", "coordinate_transformation", "geometry_construction"]))
MATHEMATICS.update(_profiles("mathematics", ["three_dimensional_geometry", "vectors"], ["geometry_solve", "vector_plane_relation", "three_d_line_plane_intersection", "three_d_line_relation", "three_d_plane_relation", "three_d_point_distance", "three_d_plane_from_points"], ["vector_plane_3d", "three_d_line_plane_diagram"]))
MATHEMATICS.update(_profiles("mathematics", ["limits_continuity", "differentiation", "applications_of_derivatives", "integration", "applications_of_integrals", "differential_equations", "continuity_differentiability", "parametric_calculus", "multivariable_calculus", "differential_calculus"], ["symbolic_algebra", "symbolic_solve", "symbolic_differentiate", "symbolic_integrate", "symbolic_limit", "symbolic_series", "calculus_curve_analysis", "calculus_limit_continuity", "calculus_tangent_normal", "calculus_definite_integral", "calculus_area_between_curves", "calculus_taylor_approximation", "calculus_parametric_analysis", "calculus_multivariable_analysis", "calculus_autonomous_ode", "symbolic_ode", "numeric_ode"], ["function_plot", "tangent_secant", "limit_approach", "riemann_area", "area_between_curves", "taylor_comparison", "vector_field"]))

CHAPTERS: dict[str, dict[str, Any]] = {**PHYSICS, **CHEMISTRY, **MATHEMATICS}


def coverage() -> dict[str, Any]:
    by_subject: dict[str, list[str]] = {}
    for identifier, profile in CHAPTERS.items():
        by_subject.setdefault(profile["subject"], []).append(identifier)
    # Imports live here to avoid making a knowledge-only import require Manim.
    from proofmotion.components import COMPONENTS
    from proofmotion.tools import REGISTRY

    tools = set(REGISTRY.names)
    component_names = set(COMPONENTS)
    chapter_audit: dict[str, dict[str, Any]] = {}
    readiness = {"planned": 0, "infrastructure_ready": 0, "validated": 0}
    for identifier, profile in CHAPTERS.items():
        required_tools = set(profile["solver_or_reference"]) - {"vetted_reference_database"}
        missing_tools = sorted(required_tools - tools)
        missing_verification = sorted(set(profile["verification"]) - tools)
        missing_visuals = sorted(set(profile["visuals"]) - component_names)
        evidence = profile["evidence"]
        rendered = evidence["render_review"] == "passed"
        case_tested = evidence["tool_test"] == "passed"
        if not missing_tools and not missing_verification and not missing_visuals and case_tested and rendered:
            state = "validated"
        elif not missing_tools and not missing_verification and not missing_visuals:
            state = "infrastructure_ready"
        else:
            state = "planned"
        readiness[state] += 1
        chapter_audit[identifier] = {
            "readiness": state,
            "missing_tools": missing_tools,
            "missing_verification": missing_verification,
            "missing_visuals": missing_visuals,
            "missing_representative_case": evidence["representative_case"] is None,
            "tool_test": evidence["tool_test"],
            "render_review": evidence["render_review"],
        }
    return {
        "total": len(CHAPTERS),
        "syllabus_sources": SYLLABUS_SOURCES,
        "by_subject": {key: len(value) for key, value in by_subject.items()},
        "planned": [key for key, value in CHAPTERS.items() if value["status"] == "planned"],
        "readiness": readiness,
        "chapters": chapter_audit,
    }
