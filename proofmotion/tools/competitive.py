"""Deterministic helpers for common JEE Advanced / competitive-exam patterns.

These are deliberately small, transparent solvers.  They provide checked
quantities to the planning agent; they do not replace the derivation that the
viewer needs to see.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from proofmotion.runtime.registry import ToolError, tool

_TOPICS: dict[str, dict[str, Any]] = {
    "mechanics": {
        "words": ("motion", "kinematic", "brake", "projectile", "collision", "orbit", "circular", "oscillation", "pendulum", "spring", "rotation"),
        "tools": ["jee_mechanics", "units_check", "plausibility_check", "component_search"],
        "checks": ["state the sign convention", "show a labelled force or motion diagram", "check units and a limiting case"],
    },
    "electricity_magnetism": {
        "words": ("electric", "charge", "capacitor", "circuit", "current", "magnetic", "induction", "lens", "mirror"),
        "tools": ["symbolic_solve", "numeric_evaluate", "units_check", "component_search"],
        "checks": ["draw the circuit, field, or ray diagram before equations", "state the direction convention", "check units"],
    },
    "physical_chemistry": {
        "words": ("mole", "stoichi", "gas", "molar", "equilibrium", "ph", "acid", "base", "thermodynamic", "enthalpy", "electrochem", "kinetics"),
        "tools": ["stoichiometry_limit", "ideal_gas_state", "weak_acid_ph", "units_check", "component_search"],
        "checks": ["write the balanced reaction or ICE table", "keep units beside every conversion", "state any approximation and verify it"],
    },
    "organic_inorganic": {
        "words": ("organic", "reagent", "reaction", "isomer", "hybridisation", "coordination", "periodic", "oxidation state"),
        "tools": ["competitive_exam_requirements", "component_search"],
        "checks": ["show the structural formula or orbital diagram", "name every reagent and condition", "do not claim a reaction product without a verified chemistry reference"],
    },
    "calculus": {
        "words": ("derivative", "integral", "limit", "differential", "area", "maxima", "minima", "continuity"),
        "tools": ["symbolic_differentiate", "symbolic_integrate", "symbolic_limit", "symbolic_verify_equality", "component_search"],
        "checks": ["state the domain", "show the graph or geometric interpretation", "check endpoints where relevant"],
    },
    "algebra": {
        "words": ("quadratic", "complex", "sequence", "series", "permutation", "combination", "probability", "matrix", "determinant", "vector"),
        "tools": ["symbolic_algebra", "symbolic_solve", "symbolic_matrix", "combinatorics", "probability", "counterexample_search"],
        "checks": ["state restrictions before cancelling or squaring", "test roots in the original equation", "draw a diagram when a geometric interpretation exists"],
    },
    "coordinate_geometry": {
        "words": ("circle", "parabola", "ellipse", "hyperbola", "coordinate", "triangle", "conic", "locus"),
        "tools": ["geometry_solve", "conic_properties", "symbolic_solve", "component_search"],
        "checks": ["draw and label the coordinate diagram", "state the coordinate convention", "verify the final point or locus"],
    },
}


@tool
def competitive_exam_requirements(prompt: str) -> dict[str, Any]:
    """Classify a competitive-exam prompt and list mandatory solving safeguards.

    Use this first for JEE Advanced, JEE Main, NEET, Olympiad, or other
    multi-step PCM questions.  It does not solve the problem; it tells the
    agent which checked tools, diagrams, assumptions, and validations the
    solution must contain.

    Args:
        prompt: The full question text or a concise description of the topic.
    """
    text = prompt.lower()
    matched = [name for name, rule in _TOPICS.items() if any(word in text for word in rule["words"])]
    if not matched:
        matched = ["mechanics", "calculus", "algebra"]
    tools = list(dict.fromkeys(tool for name in matched for tool in _TOPICS[name]["tools"]))
    checks = list(dict.fromkeys(check for name in matched for check in _TOPICS[name]["checks"]))
    chemistry_reference = "organic_inorganic" in matched
    return {
        "matched_domains": matched,
        "required_tools": tools,
        "required_solution_structure": [
            "given quantities and unknowns",
            "labelled diagram or graph before the derivation",
            "one justified transformation per displayed step",
            "substitution with units",
            "boxed final answer with units or conditions",
        ],
        "required_checks": checks,
        "requires_verified_chemistry_reference": chemistry_reference,
        "note": (
            "Organic/inorganic reaction predictions need a curated reaction/reference database; "
            "the current deterministic tools must not invent reaction outcomes."
            if chemistry_reference else "Use the returned tools to compute values; do not calculate them from memory."
        ),
    }


@tool
def jee_mechanics(
    problem_type: Literal["uniform_acceleration", "projectile", "inverse_square_orbit", "small_radial_kepler"],
    initial_velocity: float | None = None,
    final_velocity: float | None = None,
    time: float | None = None,
    speed: float | None = None,
    angle_deg: float | None = None,
    mass: float | None = None,
    force_constant: float | None = None,
    radius: float | None = None,
    gravity: float = 9.8,
) -> dict[str, Any]:
    """Compute checked results for four frequent mechanics patterns.

    Args:
        problem_type: uniform_acceleration, projectile, inverse_square_orbit,
            or small_radial_kepler.
        initial_velocity: Initial speed/velocity for uniform acceleration.
        final_velocity: Final speed/velocity for uniform acceleration.
        time: Elapsed time for uniform acceleration.
        speed: Launch speed for a projectile.
        angle_deg: Launch angle in degrees for a projectile.
        mass: Particle mass for an inverse-square circular orbit.
        force_constant: k in F=-k/r**2 for an inverse-square orbit.
        radius: Circular-orbit radius r0.
        gravity: Positive magnitude of gravitational acceleration for a projectile.
    """
    if problem_type == "uniform_acceleration":
        if initial_velocity is None or final_velocity is None or time is None or time <= 0:
            raise ToolError("uniform_acceleration needs initial_velocity, final_velocity, and positive time")
        acceleration = (final_velocity - initial_velocity) / time
        distance = (initial_velocity + final_velocity) * time / 2
        return {
            "model": "constant acceleration", "acceleration": acceleration, "distance": distance,
            "equations": ["a=(v-u)/t", "s=(u+v)t/2"],
            "units": {"acceleration": "m/s^2", "distance": "m"},
        }
    if problem_type == "projectile":
        if speed is None or angle_deg is None or gravity <= 0:
            raise ToolError("projectile needs speed, angle_deg, and positive gravity")
        theta = math.radians(angle_deg)
        return {
            "model": "projectile returning to launch height",
            "horizontal_speed": speed * math.cos(theta),
            "vertical_speed": speed * math.sin(theta),
            "time_of_flight": 2 * speed * math.sin(theta) / gravity,
            "maximum_height": speed**2 * math.sin(theta) ** 2 / (2 * gravity),
            "range": speed**2 * math.sin(2 * theta) / gravity,
            "units": {"speed": "m/s", "time_of_flight": "s", "maximum_height": "m", "range": "m"},
        }
    if mass is None or force_constant is None or radius is None or min(mass, force_constant, radius) <= 0:
        raise ToolError(f"{problem_type} needs positive mass, force_constant k, and radius r0")
    angular_momentum = math.sqrt(mass * force_constant * radius)
    omega_squared = force_constant / (mass * radius**3)
    period = 2 * math.pi / math.sqrt(omega_squared)
    common = {
        "condition": "l^2 = m*k*r0", "angular_momentum": angular_momentum,
        "angular_frequency_squared": omega_squared, "period": period,
        "period_from_l": 2 * math.pi * mass * radius**2 / angular_momentum,
        "units": {"period": "s"},
    }
    if problem_type == "inverse_square_orbit":
        common["model"] = "circular orbit under F=-k/r^2"
    else:
        common["model"] = "small radial oscillation about an inverse-square circular orbit"
        common["derivation_hint"] = "Use U_eff=l^2/(2*m*r^2)-k/r; then omega_r^2=U_eff''(r0)/m."
    return common


@tool
def stoichiometry_limit(
    reactant_moles: list[float],
    reactant_coefficients: list[float],
    product_coefficient: float = 1.0,
    product_molar_mass: float | None = None,
) -> dict[str, Any]:
    """Find the limiting reactant and theoretical product for a balanced reaction.

    Args:
        reactant_moles: Initial amount of each reactant in mol, in balanced-equation order.
        reactant_coefficients: Matching positive balanced coefficients.
        product_coefficient: Balanced coefficient of the requested product.
        product_molar_mass: Optional product molar mass in g/mol.
    """
    if len(reactant_moles) != len(reactant_coefficients) or not reactant_moles:
        raise ToolError("supply one positive coefficient and mole amount for every reactant")
    if any(n < 0 for n in reactant_moles) or any(c <= 0 for c in reactant_coefficients) or product_coefficient <= 0:
        raise ToolError("moles must be non-negative and coefficients must be positive")
    extents = [n / c for n, c in zip(reactant_moles, reactant_coefficients, strict=True)]
    extent = min(extents)
    limiting = [index for index, value in enumerate(extents) if math.isclose(value, extent, rel_tol=1e-10, abs_tol=1e-12)]
    product_moles = extent * product_coefficient
    result: dict[str, Any] = {
        "reaction_extent_mol": extent, "limiting_reactant_indices": limiting,
        "product_moles": product_moles, "excess_reactant_moles": [max(0.0, n - extent * c) for n, c in zip(reactant_moles, reactant_coefficients, strict=True)],
    }
    if product_molar_mass is not None:
        if product_molar_mass <= 0:
            raise ToolError("product_molar_mass must be positive")
        result["product_mass_g"] = product_moles * product_molar_mass
    return result


@tool
def ideal_gas_state(pressure_pa: float, volume_m3: float, moles: float, temperature_k: float) -> dict[str, Any]:
    """Check a gas state against PV=nRT and report the ideal-gas residual.

    Args:
        pressure_pa: Absolute pressure in Pa.
        volume_m3: Volume in m^3.
        moles: Amount in mol.
        temperature_k: Absolute temperature in K.
    """
    if min(pressure_pa, volume_m3, moles, temperature_k) <= 0:
        raise ToolError("pressure, volume, moles, and absolute temperature must all be positive")
    r = 8.314462618
    pv, nrt = pressure_pa * volume_m3, moles * r * temperature_k
    return {
        "equation": "P*V=n*R*T", "PV_joule": pv, "nRT_joule": nrt,
        "residual_joule": pv - nrt, "relative_residual": abs(pv - nrt) / nrt,
        "consistent_with_ideal_gas": math.isclose(pv, nrt, rel_tol=1e-6),
    }


@tool
def weak_acid_ph(concentration_molar: float, ka: float) -> dict[str, Any]:
    """Solve a monoprotic weak-acid equilibrium exactly and test the usual approximation.

    Args:
        concentration_molar: Initial acid concentration C in mol/L.
        ka: Acid dissociation constant Ka.
    """
    if concentration_molar <= 0 or ka <= 0:
        raise ToolError("concentration_molar and ka must be positive")
    # Ka=x^2/(C-x), hence x^2+Ka*x-Ka*C=0.  The positive root is physical.
    hydrogen = (-ka + math.sqrt(ka**2 + 4 * ka * concentration_molar)) / 2
    approximation = math.sqrt(ka * concentration_molar)
    dissociation_fraction = hydrogen / concentration_molar
    return {
        "hydrogen_molar": hydrogen, "ph": -math.log10(hydrogen),
        "sqrt_ka_c_approximation": approximation,
        "approximation_error_fraction": abs(approximation - hydrogen) / hydrogen,
        "five_percent_rule_holds": dissociation_fraction <= 0.05,
        "dissociation_fraction": dissociation_fraction,
    }
