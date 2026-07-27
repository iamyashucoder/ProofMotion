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
        "words": ("motion", "kinematic", "brake", "projectile", "collision", "orbit", "circular", "oscillation", "pendulum", "spring", "rotation", "friction", "finger", "meter scale", "metre scale"),
        "tools": ["jee_mechanics", "meter_scale_alternating_friction", "units_check", "plausibility_check", "component_search"],
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
def meter_scale_alternating_friction(
    left_initial_cm: float,
    right_initial_cm: float,
    static_friction: float,
    dynamic_friction: float,
    center_cm: float = 50.0,
) -> dict[str, Any]:
    """Solve the alternating-slip meter-scale-on-two-fingers problem exactly.

    At each switch, the sliding finger has dynamic friction mu_k*N while the
    fixed finger is at limiting static friction mu_s*N.  The scale is uniform,
    so its support reactions are found by taking moments about its centre.
    """
    if not (0 < dynamic_friction < static_friction):
        raise ToolError("require positive coefficients with dynamic_friction < static_friction")
    if not left_initial_cm < center_cm < right_initial_cm:
        raise ToolError("the two initial finger positions must straddle the scale centre")
    right_distance = right_initial_cm - center_cm
    # Left slips first, right remains fixed: mu_k N_L = mu_s N_R.
    left_after_first = center_cm - dynamic_friction * right_distance / static_friction
    left_distance = center_cm - left_after_first
    # Right then slips, left remains fixed: mu_k N_R = mu_s N_L.
    right_after_second = center_cm + dynamic_friction * left_distance / static_friction
    return {
        "left_position_at_first_switch_cm": left_after_first,
        "right_position_at_second_switch_cm": right_after_second,
        "x_right_from_center_cm": right_after_second - center_cm,
        "switch_1_condition": r"mu_k N_L=mu_s N_R",
        "switch_2_condition": r"mu_k N_R=mu_s N_L",
        "support_reactions": r"N_L=W(x_R-50)/(x_R-x_L), N_R=W(50-x_L)/(x_R-x_L)",
        "final_answer": f"x_R={right_after_second - center_cm:.2f} cm",
    }


@tool
def linear_drag_projectile(
    mass_kg: float,
    drag_coefficient_kg_per_s: float,
    launch_speed: float,
    angle_deg: float,
    time_s: float,
    gravity: float = 9.8,
    e_approx: float | None = None,
) -> dict[str, Any]:
    """Solve a projectile exactly when drag force is F_drag=-c*v.

    The horizontal coordinate is x(t)=u*cos(theta)*(1-exp(-c*t/m))/(c/m).
    Use this rather than the parabolic no-drag range formula.

    Args:
        mass_kg: Projectile mass in kg.
        drag_coefficient_kg_per_s: Linear drag coefficient c in kg/s.
        launch_speed: Initial speed u in m/s.
        angle_deg: Launch angle above horizontal in degrees.
        time_s: Time at which the wall is struck, in seconds.
        gravity: Positive gravitational acceleration in m/s^2.
        e_approx: Optional supplied approximation for e, e.g. 2.7. When set,
            use this only because the question explicitly requests it.
    """
    if min(mass_kg, drag_coefficient_kg_per_s, launch_speed, time_s, gravity) <= 0 or not 0 < angle_deg < 90:
        raise ToolError("mass, drag, speed, time, and gravity must be positive; angle_deg must lie between 0 and 90")
    beta = drag_coefficient_kg_per_s / mass_kg
    theta = math.radians(angle_deg)
    decay = math.exp(-beta * time_s) if e_approx is None else e_approx ** (-beta * time_s)
    ux, uy = launch_speed * math.cos(theta), launch_speed * math.sin(theta)
    x = ux * (1 - decay) / beta
    y = (uy + gravity / beta) * (1 - decay) / beta - gravity * time_s / beta
    vx = ux * decay
    vy = (uy + gravity / beta) * decay - gravity / beta
    return {
        "beta_per_s": beta, "decay_factor": decay,
        "used_e_approximation": e_approx,
        "initial_components_m_per_s": {"ux": ux, "uy": uy},
        "position_at_time_m": {"x": x, "y": y},
        "velocity_at_time_m_per_s": {"vx": vx, "vy": vy},
        "horizontal_equation": "x(t)=u*cos(theta)*(1-exp(-(c/m)t))/(c/m)",
        "vertical_equation": "y(t)=(u*sin(theta)+g/(c/m))*(1-exp(-(c/m)t))/(c/m)-g*t/(c/m)",
    }


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
def ac_phasor_analysis(voltage_rms: float, current_rms: float, phase_deg: float) -> dict[str, Any]:
    """Compute AC power, reactive power, and power factor from RMS phasors."""
    if voltage_rms <= 0 or current_rms <= 0 or not -90 <= phase_deg <= 90:
        raise ToolError("RMS values must be positive and phase_deg must lie between -90 and 90")
    phase = math.radians(phase_deg)
    return {"apparent_power_va": voltage_rms * current_rms, "power_factor": math.cos(phase), "real_power_w": voltage_rms * current_rms * math.cos(phase), "reactive_power_var": voltage_rms * current_rms * math.sin(phase), "current_relation": "lagging" if phase_deg < 0 else "leading" if phase_deg > 0 else "in phase"}


@tool
def electromagnetic_induction(turns: int, flux_initial_wb: float, flux_final_wb: float, interval_s: float) -> dict[str, Any]:
    """Apply Faraday's law to compute induced emf and Lenz-law opposition."""
    if turns <= 0 or interval_s <= 0:
        raise ToolError("turns and interval_s must be positive")
    flux_change = flux_final_wb - flux_initial_wb
    emf = -turns * flux_change / interval_s
    return {"flux_change_wb": flux_change, "induced_emf_v": emf, "emf_magnitude_v": abs(emf), "law": "emf=-N*DeltaPhi/Delta t", "lenz_law": "induced current opposes the change in magnetic flux"}


@tool
def wave_optics(
    mode: Literal["double_slit", "single_slit"], wavelength_nm: float, screen_distance_m: float, aperture_mm: float,
) -> dict[str, Any]:
    """Compute double-slit fringe spacing or single-slit first-minimum distance."""
    if min(wavelength_nm, screen_distance_m, aperture_mm) <= 0:
        raise ToolError("wavelength, screen distance, and aperture must be positive")
    distance = wavelength_nm * 1e-9 * screen_distance_m / (aperture_mm * 1e-3)
    return {"mode": mode, "distance_m": distance, "distance_mm": distance * 1000, "equation": "beta=lambda*D/d" if mode == "double_slit" else "y_1=lambda*D/a"}


@tool
def fluid_flow_bernoulli(area_1: float, area_2: float, speed_1: float, pressure_1_pa: float, density: float = 1000.0, height_1_m: float = 0.0, height_2_m: float = 0.0, gravity: float = 9.8) -> dict[str, Any]:
    """Use continuity and Bernoulli equations for incompressible steady flow."""
    if min(area_1, area_2, speed_1, density, gravity) <= 0:
        raise ToolError("areas, speed, density, and gravity must be positive")
    speed_2 = area_1 * speed_1 / area_2
    pressure_2 = pressure_1_pa + 0.5 * density * (speed_1**2 - speed_2**2) + density * gravity * (height_1_m - height_2_m)
    return {"speed_2_m_per_s": speed_2, "pressure_2_pa": pressure_2, "continuity": "A1*v1=A2*v2", "bernoulli": "P+rho*v^2/2+rho*g*h=constant"}


_ORGANIC_REFERENCE: dict[str, dict[str, str]] = {
    "sn1": {"mechanism": "carbocation formation followed by nucleophilic attack", "conditions": "tertiary substrate; polar protic solvent", "visual": "organic_mechanism_template"},
    "sn2": {"mechanism": "single backside nucleophilic attack", "conditions": "primary substrate; strong nucleophile", "visual": "organic_mechanism_template"},
    "e1": {"mechanism": "carbocation formation followed by deprotonation", "conditions": "tertiary substrate; polar protic solvent", "visual": "organic_mechanism_template"},
    "e2": {"mechanism": "concerted beta-hydrogen abstraction and leaving-group departure", "conditions": "strong base; anti-periplanar geometry", "visual": "organic_mechanism_template"},
}


@tool
def organic_reference_lookup(reaction_family: Literal["sn1", "sn2", "e1", "e2"]) -> dict[str, Any]:
    """Return a vetted mechanism-family reference; never predict an unlisted product."""
    return {"reaction_family": reaction_family, **_ORGANIC_REFERENCE[reaction_family], "product_prediction_allowed": False, "note": "Use a curated reaction database before naming a specific product."}


@tool
def coordination_complex_analysis(coordination_number: int, d_electrons: int, field: Literal["weak", "strong"] = "weak") -> dict[str, Any]:
    """Classify common coordination geometry and estimate d-electron unpairing."""
    if coordination_number not in {4, 6} or not 0 <= d_electrons <= 10:
        raise ToolError("support currently covers coordination number 4 or 6 and d-electron count 0..10")
    geometry = "octahedral" if coordination_number == 6 else "tetrahedral_or_square_planar"
    # Octahedral high/low spin counts; CN=4 requires ligand-specific structural evidence.
    unpaired = min(d_electrons, 10 - d_electrons) if field == "weak" else (0 if d_electrons in {0, 6, 10} else min(d_electrons, 10 - d_electrons))
    return {"geometry": geometry, "field": field, "estimated_unpaired_electrons": unpaired, "requires_ligand_evidence_for_exact_geometry": coordination_number == 4}


@tool
def vector_plane_relation(vector: list[float], plane: list[float], point: list[float] | None = None) -> dict[str, Any]:
    """Check a 3D vector against plane ax+by+cz=d and optionally project a point."""
    if len(vector) != 3 or len(plane) != 4 or (point is not None and len(point) != 3):
        raise ToolError("vector needs 3 values, plane needs [a,b,c,d], and point needs 3 values")
    a, b, c, d = map(float, plane)
    norm2 = a*a + b*b + c*c
    if norm2 == 0:
        raise ToolError("plane normal cannot be zero")
    dot = a*vector[0] + b*vector[1] + c*vector[2]
    result: dict[str, Any] = {"normal": [a, b, c], "dot_with_normal": dot, "parallel_to_plane": math.isclose(dot, 0.0, abs_tol=1e-10), "perpendicular_to_plane": vector == [a, b, c]}
    if point is not None:
        factor = (a*point[0] + b*point[1] + c*point[2] - d) / norm2
        result["point_projection"] = [point[i] - factor*[a, b, c][i] for i in range(3)]
    return result


@tool
def rigid_body_rotation(shape: Literal["ring", "disc", "solid_sphere", "solid_cylinder"], mass_kg: float, radius_m: float, torque_nm: float) -> dict[str, Any]:
    """Compute moment of inertia and angular acceleration about a symmetry axis."""
    if min(mass_kg, radius_m) <= 0:
        raise ToolError("mass_kg and radius_m must be positive")
    factors = {"ring": 1.0, "disc": 0.5, "solid_sphere": 0.4, "solid_cylinder": 0.5}
    inertia = factors[shape] * mass_kg * radius_m**2
    return {"shape": shape, "moment_of_inertia_kg_m2": inertia, "angular_acceleration_rad_per_s2": torque_nm / inertia, "equation": "tau=I*alpha"}


@tool
def centre_of_mass(masses_kg: list[float], positions_m: list[list[float]]) -> dict[str, Any]:
    """Compute centre of mass of point particles in 1D, 2D, or 3D."""
    if not masses_kg or len(masses_kg) != len(positions_m) or any(m <= 0 for m in masses_kg):
        raise ToolError("supply matching positive masses and positions")
    dimension = len(positions_m[0])
    if dimension not in {1, 2, 3} or any(len(position) != dimension for position in positions_m):
        raise ToolError("all positions must have the same dimension of 1, 2, or 3")
    total = sum(masses_kg)
    return {"total_mass_kg": total, "centre_of_mass_m": [sum(m * position[i] for m, position in zip(masses_kg, positions_m, strict=True)) / total for i in range(dimension)]}


@tool
def gravitation_orbit(mass_kg: float, central_mass_kg: float, radius_m: float, gravitational_constant: float = 6.67430e-11) -> dict[str, Any]:
    """Compute circular-orbit speed, period, gravitational field, and escape speed."""
    if min(mass_kg, central_mass_kg, radius_m, gravitational_constant) <= 0:
        raise ToolError("masses, radius, and gravitational constant must be positive")
    mu = gravitational_constant * central_mass_kg
    return {"orbital_speed_m_per_s": math.sqrt(mu / radius_m), "period_s": 2 * math.pi * math.sqrt(radius_m**3 / mu), "escape_speed_m_per_s": math.sqrt(2 * mu / radius_m), "field_m_per_s2": mu / radius_m**2}


@tool
def damped_oscillator(mass_kg: float, stiffness_n_per_m: float, damping_kg_per_s: float) -> dict[str, Any]:
    """Classify a damped spring oscillator and compute its damped frequency when applicable."""
    if min(mass_kg, stiffness_n_per_m) <= 0 or damping_kg_per_s < 0:
        raise ToolError("mass and stiffness must be positive; damping must be non-negative")
    omega0 = math.sqrt(stiffness_n_per_m / mass_kg)
    gamma = damping_kg_per_s / (2 * mass_kg)
    regime = "underdamped" if gamma < omega0 else "critical" if math.isclose(gamma, omega0) else "overdamped"
    return {"natural_angular_frequency": omega0, "damping_constant": gamma, "regime": regime, "damped_angular_frequency": math.sqrt(max(0.0, omega0**2 - gamma**2))}


@tool
def terminal_velocity_sphere(radius_m: float, sphere_density: float, fluid_density: float, viscosity_pa_s: float, gravity: float = 9.8) -> dict[str, Any]:
    """Use Stokes drag to compute a sphere's low-Reynolds-number terminal velocity."""
    if min(radius_m, sphere_density, fluid_density, viscosity_pa_s, gravity) <= 0:
        raise ToolError("all physical inputs must be positive")
    velocity = 2 * radius_m**2 * gravity * (sphere_density - fluid_density) / (9 * viscosity_pa_s)
    return {"terminal_velocity_m_per_s": velocity, "direction": "downward" if velocity > 0 else "upward", "equation": "v_t=2*r^2*g*(rho_s-rho_f)/(9*eta)"}


@tool
def radioactive_decay(initial_nuclei: float, half_life_s: float, time_s: float) -> dict[str, Any]:
    """Compute remaining nuclei, decayed fraction, and decay constant from half-life."""
    if min(initial_nuclei, half_life_s, time_s) < 0 or initial_nuclei <= 0 or half_life_s <= 0:
        raise ToolError("initial nuclei and half-life must be positive; time must be non-negative")
    decay_constant = math.log(2) / half_life_s
    remaining = initial_nuclei * math.exp(-decay_constant * time_s)
    return {"remaining_nuclei": remaining, "decayed_fraction": 1 - remaining / initial_nuclei, "decay_constant_per_s": decay_constant, "equation": "N=N0*exp(-lambda*t)"}


@tool
def elasticity_wire(force_n: float, length_m: float, area_m2: float, young_modulus_pa: float) -> dict[str, Any]:
    """Compute extension, stress, strain, and elastic energy of a uniform wire."""
    if min(length_m, area_m2, young_modulus_pa) <= 0:
        raise ToolError("length, area, and Young modulus must be positive")
    stress = force_n / area_m2
    strain = stress / young_modulus_pa
    extension = strain * length_m
    return {"stress_pa": stress, "strain": strain, "extension_m": extension, "elastic_energy_j": 0.5 * force_n * extension, "equation": "Delta L=F*L/(A*Y)"}


@tool
def surface_tension_capillary(surface_tension_n_per_m: float, radius_m: float, contact_angle_deg: float, density: float, gravity: float = 9.8) -> dict[str, Any]:
    """Compute capillary rise/depression in a circular tube from surface tension."""
    if min(surface_tension_n_per_m, radius_m, density, gravity) <= 0:
        raise ToolError("surface tension, radius, density, and gravity must be positive")
    rise = 2 * surface_tension_n_per_m * math.cos(math.radians(contact_angle_deg)) / (density * gravity * radius_m)
    return {"height_m": rise, "height_cm": rise * 100, "direction": "rise" if rise >= 0 else "depression", "equation": "h=2*T*cos(theta)/(rho*g*r)"}


@tool
def calorimetry_mix(masses_kg: list[float], specific_heats_j_per_kg_k: list[float], temperatures_k: list[float]) -> dict[str, Any]:
    """Find equilibrium temperature for insulated mixing with no phase change."""
    if not masses_kg or not (len(masses_kg) == len(specific_heats_j_per_kg_k) == len(temperatures_k)):
        raise ToolError("supply matching non-empty masses, specific heats, and temperatures")
    capacities = [m * c for m, c in zip(masses_kg, specific_heats_j_per_kg_k, strict=True)]
    if any(value <= 0 for value in capacities) or any(temp <= 0 for temp in temperatures_k):
        raise ToolError("masses, specific heats, and absolute temperatures must be positive")
    final = sum(capacity * temp for capacity, temp in zip(capacities, temperatures_k, strict=True)) / sum(capacities)
    return {"equilibrium_temperature_k": final, "heat_capacities_j_per_k": capacities, "equation": "sum(m*c*(Tf-Ti))=0"}


@tool
def doppler_effect(source_frequency_hz: float, wave_speed_m_per_s: float, observer_speed_m_per_s: float = 0.0, source_speed_m_per_s: float = 0.0, approaching: bool = True) -> dict[str, Any]:
    """Compute observed frequency for collinear source/observer motion in a medium."""
    if min(source_frequency_hz, wave_speed_m_per_s) <= 0 or abs(source_speed_m_per_s) >= wave_speed_m_per_s:
        raise ToolError("frequency and wave speed must be positive; source speed magnitude must be below wave speed")
    sign = 1 if approaching else -1
    observed = source_frequency_hz * (wave_speed_m_per_s + sign * observer_speed_m_per_s) / (wave_speed_m_per_s - sign * source_speed_m_per_s)
    return {"observed_frequency_hz": observed, "frequency_shift_hz": observed - source_frequency_hz, "equation": "f'=f*(v +/- vo)/(v -/+ vs)"}


@tool
def ray_optics(focal_length_m: float, object_distance_m: float) -> dict[str, Any]:
    """Apply the Cartesian lens formula 1/f=1/v-1/u using positive distances as magnitudes."""
    if focal_length_m == 0 or object_distance_m <= 0:
        raise ToolError("focal length must be non-zero and object distance must be positive")
    # With u=-object_distance in the Cartesian convention.
    denominator = 1 / focal_length_m - 1 / object_distance_m
    if math.isclose(denominator, 0.0, abs_tol=1e-12):
        return {"image_distance_m": None, "image_type": "at_infinity", "equation": "1/f=1/v-1/u"}
    image_distance = 1 / denominator
    magnification = image_distance / -object_distance_m
    return {"image_distance_m": image_distance, "magnification": magnification, "image_type": "real" if image_distance > 0 else "virtual", "equation": "1/f=1/v-1/u"}


@tool
def photoelectric_effect(work_function_ev: float, photon_energy_ev: float) -> dict[str, Any]:
    """Compute photoelectron kinetic energy and stopping potential from Einstein's equation."""
    if min(work_function_ev, photon_energy_ev) < 0:
        raise ToolError("work function and photon energy must be non-negative")
    kinetic = max(0.0, photon_energy_ev - work_function_ev)
    return {"emission": photon_energy_ev >= work_function_ev, "max_kinetic_energy_ev": kinetic, "stopping_potential_v": kinetic, "equation": "Kmax=Ephoton-phi"}


@tool
def semiconductor_diode(supply_voltage_v: float, resistance_ohm: float, threshold_voltage_v: float = 0.7, forward_biased: bool = True) -> dict[str, Any]:
    """Use the constant-voltage diode model to compute circuit current."""
    if resistance_ohm <= 0 or min(supply_voltage_v, threshold_voltage_v) < 0:
        raise ToolError("resistance must be positive and voltages must be non-negative")
    conducts = forward_biased and supply_voltage_v > threshold_voltage_v
    current = (supply_voltage_v - threshold_voltage_v) / resistance_ohm if conducts else 0.0
    return {"conducting": conducts, "current_a": current, "diode_voltage_v": threshold_voltage_v if conducts else supply_voltage_v, "model": "constant-voltage diode"}


@tool
def heat_conduction(conductivity_w_per_m_k: float, area_m2: float, temperature_hot_k: float, temperature_cold_k: float, thickness_m: float) -> dict[str, Any]:
    """Compute steady one-dimensional conductive heat flow through a slab."""
    if min(conductivity_w_per_m_k, area_m2, thickness_m, temperature_hot_k, temperature_cold_k) <= 0:
        raise ToolError("conductivity, area, thickness, and absolute temperatures must be positive")
    rate = conductivity_w_per_m_k * area_m2 * (temperature_hot_k - temperature_cold_k) / thickness_m
    return {"heat_flow_rate_w": rate, "direction": "hot_to_cold" if rate >= 0 else "cold_to_hot", "equation": "Qdot=k*A*(Th-Tc)/L"}


@tool
def rlc_resonance(resistance_ohm: float, inductance_h: float, capacitance_f: float, voltage_rms_v: float) -> dict[str, Any]:
    """Compute series-RLC resonance frequency, quality factor, and resonant current."""
    if min(resistance_ohm, inductance_h, capacitance_f, voltage_rms_v) <= 0:
        raise ToolError("resistance, inductance, capacitance, and voltage must be positive")
    angular = 1 / math.sqrt(inductance_h * capacitance_f)
    return {"resonant_angular_frequency_rad_per_s": angular, "resonant_frequency_hz": angular / (2 * math.pi), "quality_factor": angular * inductance_h / resistance_ohm, "resonant_current_a": voltage_rms_v / resistance_ohm, "equation": "omega0=1/sqrt(LC)"}


@tool
def polarization_malus(initial_intensity: float, angle_deg: float) -> dict[str, Any]:
    """Apply Malus's law to ideal polarizers."""
    if initial_intensity < 0:
        raise ToolError("initial intensity must be non-negative")
    transmitted = initial_intensity * math.cos(math.radians(angle_deg)) ** 2
    return {"transmitted_intensity": transmitted, "transmission_fraction": transmitted / initial_intensity if initial_intensity else 0.0, "equation": "I=I0*cos^2(theta)"}


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
