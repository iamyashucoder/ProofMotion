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
        "words": ("electric", "power plant", "transformer", "transmission", "charge", "capacitor", "circuit", "current", "magnetic", "induction", "lens", "mirror"),
        "tools": ["power_transmission", "symbolic_solve", "numeric_evaluate", "units_check", "component_search"],
        "checks": ["draw the circuit, field, or ray diagram before equations", "state the direction convention", "check units"],
    },
    "thermal_waves_optics": {
        "words": ("thermodynamic", "heat", "engine", "entropy", "wave", "sound", "doppler", "interference", "diffraction", "optics", "lens", "mirror"),
        "tools": ["thermodynamic_process", "symbolic_solve", "units_check", "component_search"],
        "checks": ["draw the process path or ray/wavefront diagram", "state the sign convention for work and heat", "check the limiting case"],
    },
    "modern_physics": {
        "words": ("hydrogen", "bohr", "photon", "photoelectric", "nuclear", "radioactive", "semiconductor", "de broglie"),
        "tools": ["hydrogen_transition", "numeric_evaluate", "units_check", "component_search"],
        "checks": ["write the energy-level or band diagram", "keep eV and joule conversions explicit", "state emission versus absorption"],
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


_CATALOGUE: dict[str, dict[str, Any]] = {
    "physics_mechanics": {"coverage": "deterministic", "tools": ["jee_mechanics", "numeric_ode", "units_check"], "visuals": ["free_body_diagram", "projectile_motion", "circular_motion", "pendulum", "spring_mass", "collision"]},
    "physics_electricity_magnetism": {"coverage": "deterministic core", "tools": ["circuit_network", "capacitor_network", "electrostatics_point_charges", "power_transmission", "units_check"], "visuals": ["circuit_diagram", "field_lines", "power_transmission_diagram"]},
    "physics_thermal_waves_optics": {"coverage": "deterministic core", "tools": ["thermodynamic_process", "symbolic_solve", "numeric_sample"], "visuals": ["pv_diagram", "wave_form", "standing_wave", "ray_diagram"]},
    "physics_modern": {"coverage": "deterministic core", "tools": ["hydrogen_transition", "numeric_evaluate", "units_check"], "visuals": ["energy_bars"]},
    "chemistry_physical": {"coverage": "deterministic core", "tools": ["stoichiometry_limit", "ideal_gas_state", "weak_acid_ph", "chemical_equilibrium_direction", "thermodynamic_process"], "visuals": ["pv_diagram", "energy_bars"]},
    "chemistry_organic": {"coverage": "requires curated reaction database", "tools": ["competitive_exam_requirements"], "visuals": ["structural-formula and mechanism components: pending"]},
    "chemistry_inorganic": {"coverage": "requires curated periodic/reaction database", "tools": ["competitive_exam_requirements"], "visuals": ["orbital and coordination components: pending"]},
    "math_algebra_calculus": {"coverage": "deterministic", "tools": ["symbolic_algebra", "symbolic_solve", "symbolic_differentiate", "symbolic_integrate", "symbolic_limit", "symbolic_series"], "visuals": ["function_plot", "tangent_secant", "riemann_area", "iteration_trace"]},
    "math_coordinate_vector": {"coverage": "deterministic", "tools": ["geometry_solve", "conic_properties", "symbolic_matrix", "symbolic_vector_calculus"], "visuals": ["geometry_construction", "matrix_transform", "vector_field", "unit_circle"]},
    "math_discrete_probability": {"coverage": "deterministic", "tools": ["combinatorics", "number_theory", "probability", "graph_algorithm"], "visuals": ["array_cells", "distribution_plot"]},
}


@tool
def competitive_exam_catalogue(subject: Literal["all", "physics", "chemistry", "mathematics"] = "all") -> dict[str, Any]:
    """Return the supported JEE/competitive-exam capability map and known gaps.

    Use this before planning a broad exam topic. It prevents an agent from
    pretending that a chemistry reaction database or a visual component already
    exists when it does not.

    Args:
        subject: all, physics, chemistry, or mathematics.
    """
    prefixes = {"physics": "physics_", "chemistry": "chemistry_", "mathematics": "math_"}
    selected = _CATALOGUE if subject == "all" else {key: value for key, value in _CATALOGUE.items() if key.startswith(prefixes[subject])}
    gaps = [key for key, value in selected.items() if "requires curated" in value["coverage"]]
    return {"subject": subject, "domains": selected, "known_gaps": gaps, "policy": "Use deterministic tools where listed; request a vetted reference dataset for every known gap."}


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
def power_transmission(
    power_kw: float,
    generation_voltage: float,
    step_up_primary_to_secondary: float,
    consumer_voltage: float,
) -> dict[str, Any]:
    """Solve an ideal-transformer power-transmission setup exactly.

    Use when a power plant raises voltage for a resistive transmission line and
    lowers it again for consumers. The cable resistance is not needed to find
    the turns ratio; if it is unspecified, this reports the negligible-drop
    ideal result and the I-squared-R loss reduction factor.

    Args:
        power_kw: Power generated and supplied, in kW.
        generation_voltage: Plant-side RMS voltage before the step-up transformer, in V.
        step_up_primary_to_secondary: N_primary/N_secondary for the step-up transformer.
        consumer_voltage: Required RMS voltage at consumers, in V.
    """
    if min(power_kw, generation_voltage, step_up_primary_to_secondary, consumer_voltage) <= 0:
        raise ToolError("power, both voltages, and the turns ratio must be positive")
    power_w = power_kw * 1000
    transmission_voltage = generation_voltage / step_up_primary_to_secondary
    plant_current = power_w / generation_voltage
    line_current = power_w / transmission_voltage
    return {
        "power_w": power_w,
        "plant_current_a": plant_current,
        "transmission_voltage_v": transmission_voltage,
        "line_current_a": line_current,
        "step_down_primary_to_secondary": transmission_voltage / consumer_voltage,
        "step_down_ratio": f"{transmission_voltage / consumer_voltage:g}:1",
        "line_loss_reduction_factor": (plant_current / line_current) ** 2,
        "derivation": [
            "V_s/V_p=N_s/N_p for an ideal transformer",
            "P=V*I at unity power factor",
            "P_loss=I^2*R, so the loss ratio follows from the current ratio squared",
            f"N_p/N_s=V_p/V_s={transmission_voltage:g}/{consumer_voltage:g}",
        ],
        "assumption": "Cable voltage drop is neglected for the turns-ratio calculation because no cable resistance was supplied.",
        "units": {"power_w": "W", "plant_current_a": "A", "transmission_voltage_v": "V", "line_current_a": "A"},
    }


@tool
def circuit_network(
    resistances_ohm: list[float],
    supply_voltage: float,
    arrangement: Literal["series", "parallel"] = "series",
) -> dict[str, Any]:
    """Solve a DC series or parallel resistor network with power checks.

    Args:
        resistances_ohm: Positive resistor values in ohms.
        supply_voltage: Ideal supply voltage in V.
        arrangement: series or parallel.
    """
    if not resistances_ohm or any(value <= 0 for value in resistances_ohm) or supply_voltage <= 0:
        raise ToolError("resistances and supply_voltage must be positive")
    if arrangement == "series":
        equivalent = sum(resistances_ohm)
        current = supply_voltage / equivalent
        branch_currents = [current] * len(resistances_ohm)
        branch_voltages = [current * value for value in resistances_ohm]
    else:
        equivalent = 1 / sum(1 / value for value in resistances_ohm)
        current = supply_voltage / equivalent
        branch_currents = [supply_voltage / value for value in resistances_ohm]
        branch_voltages = [supply_voltage] * len(resistances_ohm)
    powers = [voltage * current for voltage, current in zip(branch_voltages, branch_currents, strict=True)]
    return {"arrangement": arrangement, "equivalent_resistance_ohm": equivalent, "total_current_a": current, "branch_currents_a": branch_currents, "branch_voltages_v": branch_voltages, "branch_powers_w": powers, "total_power_w": supply_voltage * current, "checks": {"power_sum_w": sum(powers), "power_conserved": math.isclose(sum(powers), supply_voltage * current, rel_tol=1e-10)}}


@tool
def capacitor_network(
    capacitances_farad: list[float],
    supply_voltage: float,
    arrangement: Literal["series", "parallel"] = "series",
) -> dict[str, Any]:
    """Solve a series or parallel capacitor network, including charge and energy.

    Args:
        capacitances_farad: Positive capacitances in F.
        supply_voltage: Applied voltage in V.
        arrangement: series or parallel.
    """
    if not capacitances_farad or any(value <= 0 for value in capacitances_farad) or supply_voltage <= 0:
        raise ToolError("capacitances and supply_voltage must be positive")
    if arrangement == "series":
        equivalent = 1 / sum(1 / value for value in capacitances_farad)
        charge = equivalent * supply_voltage
        charges = [charge] * len(capacitances_farad)
        voltages = [charge / value for value in capacitances_farad]
    else:
        equivalent = sum(capacitances_farad)
        charges = [value * supply_voltage for value in capacitances_farad]
        voltages = [supply_voltage] * len(capacitances_farad)
        charge = sum(charges)
    energies = [0.5 * value * voltage**2 for value, voltage in zip(capacitances_farad, voltages, strict=True)]
    return {"arrangement": arrangement, "equivalent_capacitance_f": equivalent, "total_charge_c": charge, "capacitor_charges_c": charges, "capacitor_voltages_v": voltages, "stored_energies_j": energies, "total_energy_j": 0.5 * equivalent * supply_voltage**2}


@tool
def electrostatics_point_charges(
    source_charges_c: list[list[float]],
    at: list[float],
    test_charge_c: float = 1.0,
) -> dict[str, Any]:
    """Compute electric field, potential, and force from point charges in 2D.

    Args:
        source_charges_c: Entries [charge_coulomb, x_m, y_m].
        at: Evaluation point [x_m, y_m].
        test_charge_c: Test charge for the reported force, in C.
    """
    if len(at) != 2 or not source_charges_c:
        raise ToolError("provide at=[x,y] and at least one source charge [q,x,y]")
    k = 8.9875517923e9
    ex = ey = potential = 0.0
    for entry in source_charges_c:
        if len(entry) != 3:
            raise ToolError("each source charge must be [charge_coulomb, x_m, y_m]")
        charge, x, y = map(float, entry)
        dx, dy = at[0] - x, at[1] - y
        radius_squared = dx * dx + dy * dy
        if radius_squared == 0:
            raise ToolError("field is undefined at a source-charge position")
        radius = math.sqrt(radius_squared)
        factor = k * charge / (radius_squared * radius)
        ex += factor * dx
        ey += factor * dy
        potential += k * charge / radius
    return {"field_n_per_c": [ex, ey], "field_magnitude_n_per_c": math.hypot(ex, ey), "potential_v": potential, "force_on_test_charge_n": [test_charge_c * ex, test_charge_c * ey]}


@tool
def thermodynamic_process(
    moles: float,
    initial_temperature_k: float,
    final_temperature_k: float,
    process: Literal["isochoric", "isobaric"],
    gamma: float = 1.4,
) -> dict[str, Any]:
    """Compute Q, W, and ΔU for an ideal-gas isochoric or isobaric process.

    Sign convention: positive W is work done by the gas, and Q=ΔU+W.

    Args:
        moles: Gas amount in mol.
        initial_temperature_k: Initial absolute temperature in K.
        final_temperature_k: Final absolute temperature in K.
        process: isochoric or isobaric.
        gamma: Heat-capacity ratio Cp/Cv, greater than one.
    """
    if min(moles, initial_temperature_k, final_temperature_k) <= 0 or gamma <= 1:
        raise ToolError("moles and temperatures must be positive, and gamma must exceed 1")
    r = 8.314462618
    delta_t = final_temperature_k - initial_temperature_k
    delta_u = moles * r / (gamma - 1) * delta_t
    work = 0.0 if process == "isochoric" else moles * r * delta_t
    return {"process": process, "delta_temperature_k": delta_t, "delta_u_j": delta_u, "work_by_gas_j": work, "heat_added_j": delta_u + work, "sign_convention": "Q=DeltaU+W, where W is work done by the gas"}


@tool
def hydrogen_transition(n_initial: int, n_final: int) -> dict[str, Any]:
    """Solve a hydrogen-atom transition using Bohr energy levels.

    Args:
        n_initial: Initial principal quantum number, at least 1.
        n_final: Final principal quantum number, at least 1 and different from n_initial.
    """
    if min(n_initial, n_final) < 1 or n_initial == n_final:
        raise ToolError("n_initial and n_final must be positive, distinct integers")
    emitted_energy_ev = 13.6 * abs(1 / n_final**2 - 1 / n_initial**2)
    return {"transition": f"{n_initial}->{n_final}", "kind": "emission" if n_initial > n_final else "absorption", "photon_energy_ev": emitted_energy_ev, "photon_energy_j": emitted_energy_ev * 1.602176634e-19, "wavelength_nm": 1239.841984 / emitted_energy_ev}


@tool
def chemical_equilibrium_direction(reaction_quotient: float, equilibrium_constant: float) -> dict[str, Any]:
    """Determine the equilibrium shift from Qc and Kc without guessing.

    Args:
        reaction_quotient: Current Qc, non-negative.
        equilibrium_constant: Positive Kc at the given temperature.
    """
    if reaction_quotient < 0 or equilibrium_constant <= 0:
        raise ToolError("reaction_quotient must be non-negative and equilibrium_constant must be positive")
    if math.isclose(reaction_quotient, equilibrium_constant, rel_tol=1e-9, abs_tol=1e-12):
        direction = "already at equilibrium"
    elif reaction_quotient < equilibrium_constant:
        direction = "forward, toward products"
    else:
        direction = "reverse, toward reactants"
    return {"Q": reaction_quotient, "K": equilibrium_constant, "direction": direction}


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
