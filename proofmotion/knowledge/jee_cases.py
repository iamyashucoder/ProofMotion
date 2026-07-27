"""Known-answer representative cases for every JEE syllabus profile.

The cases exercise the deterministic tool or reference guard selected for a
chapter.  They deliberately do not mark a chapter render-approved: that needs
an actual reviewed video, which is stored separately in project evidence.
"""

from __future__ import annotations

from typing import Any

from proofmotion.knowledge.jee_experts import CHAPTERS


def _case(tool: str, arguments: dict[str, Any], expected: dict[str, Any]) -> dict[str, Any]:
    return {"tool": tool, "arguments": arguments, "expected": expected}


_PHYSICS_CASES = {
    "mechanics": _case("jee_mechanics", {"problem_type": "uniform_acceleration", "initial_velocity": 20, "final_velocity": 0, "time": 4}, {"distance": 40.0}),
    "rotation": _case("rigid_body_rotation", {"shape": "disc", "mass_kg": 2, "radius_m": 1, "torque_nm": 4}, {"angular_acceleration_rad_per_s2": 4.0}),
    "fluids": _case("fluid_flow_bernoulli", {"area_1": 2, "area_2": 1, "speed_1": 3, "pressure_1_pa": 100000}, {"speed_2_m_per_s": 6.0}),
    "electricity": _case("rlc_resonance", {"resistance_ohm": 10, "inductance_h": 1, "capacitance_f": 0.25, "voltage_rms_v": 20}, {"resonant_current_a": 2.0}),
    "optics_modern": _case("photoelectric_effect", {"work_function_ev": 2, "photon_energy_ev": 5}, {"stopping_potential_v": 3.0}),
}


def _physics_case(chapter: str) -> dict[str, Any]:
    if chapter in {"circular_motion", "rigid_body_rotation", "moment_of_inertia", "angular_momentum", "rolling_motion", "gravitation", "satellites_escape_velocity", "shm", "damped_forced_oscillations", "elasticity"}:
        return _PHYSICS_CASES["rotation"]
    if chapter in {"fluid_mechanics", "viscosity_terminal_velocity", "surface_tension", "wave_motion", "sound_waves", "doppler_effect", "thermal_expansion", "calorimetry", "kinetic_theory", "thermodynamics", "heat_transfer", "blackbody_radiation"}:
        return _PHYSICS_CASES["fluids"]
    if chapter in {"electrostatics", "gauss_law", "capacitance", "current_electricity", "kirchhoff_laws", "magnetism", "magnetic_force", "electromagnetic_induction", "ac_circuits", "electromagnetic_waves"}:
        return _PHYSICS_CASES["electricity"]
    if chapter in {"ray_optics", "wave_optics", "interference", "diffraction", "polarization", "dual_nature", "atomic_physics", "nuclear_physics", "semiconductors"}:
        return _PHYSICS_CASES["optics_modern"]
    return _PHYSICS_CASES["mechanics"]


_CHEMISTRY_PHYSICAL = _case("weak_acid_ph", {"concentration_molar": 0.1, "ka": 1e-5}, {"ph": 3.002171463361816})
_CHEMISTRY_COORDINATION = _case("coordination_complex_analysis", {"coordination_number": 6, "d_electrons": 5}, {"geometry": "octahedral"})
_CHEMISTRY_ORGANIC = _case("organic_reference_lookup", {"reaction_family": "sn2"}, {"product_prediction_allowed": False})
_MATH_ALGEBRA = _case("symbolic_algebra", {"expression": "x**2-1", "operation": "factor"}, {"result": "(x - 1)*(x + 1)"})
_MATH_GEOMETRY = _case("geometry_solve", {"operation": "distance", "points": [[0, 0], [3, 4]]}, {"decimal": 5.0})
_MATH_CALCULUS = _case("symbolic_limit", {"expression": "sin(x)/x"}, {"result": "1"})


def _chapter_case(identifier: str, profile: dict[str, Any]) -> dict[str, Any]:
    if profile["subject"] == "physics":
        case = _physics_case(identifier)
    elif profile["subject"] == "chemistry":
        case = _CHEMISTRY_ORGANIC if identifier in {"basic_organic_chemistry", "isomerism", "hydrocarbons", "haloalkanes_haloarenes", "alcohols_phenols_ethers", "aldehydes_ketones", "carboxylic_acids", "amines", "biomolecules", "polymers", "chemistry_everyday_life", "practical_organic_chemistry"} else _CHEMISTRY_COORDINATION if identifier in {"periodicity", "hydrogen", "s_block", "p_block", "d_block", "f_block", "coordination_compounds", "metallurgy", "qualitative_analysis", "environmental_chemistry"} else _CHEMISTRY_PHYSICAL
    else:
        case = _MATH_GEOMETRY if identifier in {"straight_lines", "circles", "conic_sections", "locus", "three_dimensional_geometry", "vectors"} else _MATH_CALCULUS if identifier in {"limits_continuity", "differentiation", "applications_of_derivatives", "integration", "applications_of_integrals", "differential_equations"} else _MATH_ALGEBRA
    prompts = {
        "jee_mechanics": "A bus slows uniformly from 20 m/s to rest in 4 s. Find the distance travelled.",
        "rigid_body_rotation": "A uniform disc of mass 2 kg and radius 1 m experiences a 4 N m torque. Find its angular acceleration.",
        "fluid_flow_bernoulli": "Water flows from a 2 m^2 pipe section at 3 m/s into a 1 m^2 section. Find the new speed.",
        "rlc_resonance": "For a series RLC circuit at resonance with V=20 V and R=10 ohm, find the rms current.",
        "photoelectric_effect": "A metal has work function 2 eV and receives 5 eV photons. Find the stopping potential.",
        "weak_acid_ph": "Find the exact pH of 0.1 M weak acid with Ka=10^-5.",
        "coordination_complex_analysis": "Classify the geometry of a coordination-number-six complex.",
        "organic_reference_lookup": "Retrieve the verified constraints for an SN2 mechanism without predicting an unreferenced product.",
        "symbolic_algebra": "Factor x^2-1 exactly.",
        "geometry_solve": "Find the distance between (0,0) and (3,4).",
        "symbolic_limit": "Evaluate the limit of sin(x)/x as x approaches zero.",
    }
    return {"id": f"jee_{identifier}_representative", "chapter": identifier, "prompt": prompts[case["tool"]], **case}


CHAPTER_CASES: dict[str, dict[str, Any]] = {identifier: _chapter_case(identifier, profile) for identifier, profile in CHAPTERS.items()}


def execute_case(identifier: str) -> dict[str, Any]:
    """Execute one representative tool case and return its checked result."""
    from proofmotion.runtime.registry import REGISTRY

    case = CHAPTER_CASES[identifier]
    result = REGISTRY.dispatch(case["tool"], case["arguments"])
    mismatches: dict[str, dict[str, Any]] = {}
    for key, expected in case["expected"].items():
        actual = result.get(key)
        if isinstance(expected, float):
            matches = isinstance(actual, (int, float)) and abs(actual - expected) <= 1e-8 * max(1.0, abs(expected))
        else:
            matches = actual == expected
        if not matches:
            mismatches[key] = {"expected": expected, "actual": actual}
    return {"case_id": case["id"], "tool": case["tool"], "passed": not mismatches, "mismatches": mismatches}
