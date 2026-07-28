"""Tier 2 compute tools, checked against results known independently.

Every assertion here has an answer that can be looked up or derived by hand.
That is the point: a wrapper that returns something plausible is worth nothing,
and only a known answer distinguishes the two.
"""

from __future__ import annotations

import math
import unittest

import sympy as sp

from proofmotion.knowledge.jee_cases import CHAPTER_CASES, execute_case
from proofmotion.runtime.registry import ToolError
from proofmotion.tools.algebra import (
    determinant_cofactor_expansion,
    determinant_parameter_solve,
    determinant_row_effect,
    determinant_signed_area,
    matrix_arithmetic,
    matrix_linear_system,
    matrix_properties,
    matrix_row_operation,
    symbolic_algebra,
    symbolic_matrix,
    symbolic_vector_calculus,
)
from proofmotion.tools.analysis import numeric_interpolate, numeric_ode, numeric_optimize, symbolic_ode
from proofmotion.tools.calculus import (
    calculus_area_between_curves,
    calculus_autonomous_ode,
    calculus_curve_analysis,
    calculus_definite_integral,
    calculus_limit_continuity,
    calculus_multivariable_analysis,
    calculus_parametric_analysis,
    calculus_tangent_normal,
    calculus_taylor_approximation,
)
from proofmotion.tools.competitive import (
    ac_phasor_analysis,
    calorimetry_mix,
    capacitor_network,
    centre_of_mass,
    chemical_equilibrium_direction,
    circuit_network,
    competitive_exam_catalogue,
    competitive_exam_requirements,
    coordination_complex_analysis,
    damped_oscillator,
    doppler_effect,
    elasticity_wire,
    electromagnetic_induction,
    electrostatics_point_charges,
    fluid_flow_bernoulli,
    gravitation_orbit,
    heat_conduction,
    hydrogen_transition,
    ideal_gas_state,
    jee_mechanics,
    linear_drag_projectile,
    meter_scale_alternating_friction,
    organic_reference_lookup,
    photoelectric_effect,
    polarization_malus,
    power_transmission,
    radioactive_decay,
    ray_optics,
    rigid_body_rotation,
    rlc_resonance,
    semiconductor_diode,
    stoichiometry_limit,
    surface_tension_capillary,
    terminal_velocity_sphere,
    thermodynamic_process,
    vector_plane_relation,
    wave_optics,
    weak_acid_ph,
)
from proofmotion.tools.complex_numbers import (
    complex_locus,
    complex_number_analysis,
    complex_number_operation,
    complex_polynomial_roots,
    roots_of_unity,
)
from proofmotion.tools.coordinate_geometry import (
    coordinate_circle_analysis,
    coordinate_conic_classify,
    coordinate_line_analysis,
    coordinate_locus_ratio,
    coordinate_section_formula,
    coordinate_transform,
    coordinate_triangle_centres,
    hyperbola_latus_rectum_right_angle,
)
from proofmotion.tools.creator import motion_design_audit, study_animation_brief, study_animation_timing
from proofmotion.tools.discrete import combinatorics, graph_algorithm, logic_table, number_theory
from proofmotion.tools.geometry import conic_properties, geometry_solve
from proofmotion.tools.jee_experts import jee_chapter_case, jee_chapter_coverage, jee_chapter_expert
from proofmotion.tools.statistics import linear_regression, monte_carlo, probability, statistics_summary
from proofmotion.tools.three_d_geometry import (
    three_d_line_plane_intersection,
    three_d_line_relation,
    three_d_plane_from_points,
    three_d_plane_relation,
    three_d_point_distance,
)
from proofmotion.tools.trigonometry import (
    trig_equation_solve,
    trig_exact_values,
    trig_identity_check,
    trig_inverse_principal,
    trig_law_of_cosines,
    trig_law_of_sines,
    trig_wave_analysis,
)


def equivalent(left: str, right: str) -> bool:
    return sp.simplify(sp.sympify(left) - sp.sympify(right)) == 0


class CalculusTests(unittest.TestCase):
    def test_curve_analysis_finds_and_classifies_the_quadratic_minimum(self):
        result = calculus_curve_analysis("(x-2)**2+1")
        self.assertEqual(result["first_derivative"]["result"], "2*x - 4")
        self.assertEqual(result["stationary_points"][0]["x"], "2")
        self.assertEqual(result["stationary_points"][0]["classification"], "local minimum")

    def test_limit_continuity_compares_both_sides(self):
        continuous = calculus_limit_continuity("sin(x)/x", "0")
        jump = calculus_limit_continuity("1/x", "0")
        self.assertFalse(continuous["continuous"])  # removable hole: f(0) is undefined
        self.assertFalse(jump["continuous"])
        self.assertEqual(continuous["two_sided_limit"]["result"], "1")

    def test_tangent_and_definite_integral_are_exact(self):
        tangent = calculus_tangent_normal("x**2", "2")
        integral = calculus_definite_integral("x", "0", "2")
        self.assertEqual(tangent["tangent"]["result"], "Eq(y, 4*x - 4)")
        self.assertEqual(integral["value"]["result"], "2")
        self.assertEqual(integral["average_value"]["result"], "1")

    def test_area_series_parametric_multivariable_and_phase_line(self):
        area = calculus_area_between_curves("x", "x**2", "0", "1")
        series = calculus_taylor_approximation("exp(x)", "0", 2, "1")
        parametric = calculus_parametric_analysis("cos(t)", "sin(t)", "0")
        multi = calculus_multivariable_analysis("x**2+y**2", ["x", "y"], ["0", "0"])
        phase = calculus_autonomous_ode("y*(1-y)")
        self.assertEqual(area["geometric_area"]["result"], "1/6")
        self.assertEqual(series["polynomial"]["result"], "x**2/2 + x + 1")
        self.assertEqual(parametric["speed"]["result"], "1")
        self.assertEqual(multi["second_derivative_test"]["classification"], "local minimum")
        self.assertEqual([item["stability"] for item in phase["equilibria"]], ["unstable", "stable"])


class CoordinateGeometryTests(unittest.TestCase):
    def test_lines_and_circle_have_exact_intersection_and_tangent(self):
        lines = coordinate_line_analysis("x+y-3=0", "x-y-1=0")
        circle = coordinate_circle_analysis("x**2+y**2-4*x+6*y-12=0", [5, 1])
        self.assertEqual(lines["intersection"], {"x": "2", "y": "1"})
        self.assertTrue(lines["perpendicular"])
        self.assertEqual(circle["centre"], ["2", "-3"])
        self.assertEqual(circle["radius"]["result"], "5")
        self.assertTrue(circle["point_on_circle"])

    def test_conic_triangle_section_transform_and_locus(self):
        conic = coordinate_conic_classify("x**2/4 + y**2/9 - 1 = 0")
        triangle = coordinate_triangle_centres([[0, 0], [6, 0], [0, 8]])
        section = coordinate_section_formula([0, 0], [6, 3], "1", "2")
        transformed = coordinate_transform([[1, 0]], "rotate", [90])
        locus = coordinate_locus_ratio([0, 0], [4, 0], "1")
        self.assertEqual(conic["classification"], "ellipse or circle")
        self.assertEqual(triangle["centroid"], ["2", "8/3"])
        self.assertEqual(triangle["orthocentre"], ["0", "0"])
        self.assertEqual(section["point"], ["2", "1"])
        self.assertEqual(transformed["transformed"], [["0", "1"]])
        self.assertEqual(locus["classification"], "perpendicular bisector line")

    def test_hyperbola_latus_rectum_right_angle_has_a_checked_final_answer(self):
        result = hyperbola_latus_rectum_right_angle("3")
        self.assertTrue(equivalent(result["a_squared_b_squared"]["result"], "810*sqrt(2) - 1134"))
        self.assertEqual(result["alpha"], "810")
        self.assertEqual(result["beta"], "1134")
        self.assertEqual(result["alpha_plus_beta"], "1944")
        self.assertTrue(result["verification"]["equals_c_squared"])


class TrigonometryTests(unittest.TestCase):
    def test_exact_values_identity_and_interval_equation(self):
        values = trig_exact_values("30")
        identity = trig_identity_check("sin(x)**2 + cos(x)**2", "1")
        roots = trig_equation_solve("sin(x)=1/2", lower_degrees=0, upper_degrees=360)
        self.assertEqual(values["sin"]["result"], "1/2")
        self.assertEqual(values["tan"]["result"], "sqrt(3)/3")
        self.assertTrue(identity["valid"])
        self.assertEqual(roots["solutions_degrees"], ["30", "150"])

    def test_inverse_triangle_rules_and_wave_transform(self):
        inverse = trig_inverse_principal("acos", "1/2")
        cosine = trig_law_of_cosines("3", "4", "90")
        sine = trig_law_of_sines("5", "30", "90")
        wave = trig_wave_analysis("2*sin(3*(x-1))+4")
        self.assertEqual(inverse["degrees"]["result"], "60")
        self.assertEqual(cosine["third_side"]["result"], "5")
        self.assertEqual(sine["target_side"]["result"], "10")
        self.assertEqual(wave["period"]["result"], "2*pi/3")
        self.assertEqual(wave["phase_shift"]["result"], "1")


class AlgebraTests(unittest.TestCase):
    def test_rewrites_preserve_value(self):
        for expression, operation in [
            ("x**2-1", "factor"), ("(x+1)*(x-1)", "expand"),
            ("1/(x**2-1)", "apart"), ("1/x + 1/(x+1)", "together"),
        ]:
            with self.subTest(operation=operation):
                self.assertTrue(equivalent(symbolic_algebra(expression, operation)["result"], expression))

    def test_factor_actually_factors(self):
        self.assertEqual(symbolic_algebra("x**2-1", "factor")["result"], "(x - 1)*(x + 1)")

    def test_pythagorean_identity_simplifies(self):
        self.assertEqual(symbolic_algebra("sin(x)**2+cos(x)**2", "trig_simplify")["result"], "1")


class MatrixTests(unittest.TestCase):
    def test_known_determinant_rank_and_trace(self):
        self.assertEqual(symbolic_matrix([[1, 2], [3, 4]], "determinant")["result"], "-2")
        self.assertEqual(symbolic_matrix([[1, 2], [2, 4]], "rank")["result"], "1")
        self.assertEqual(symbolic_matrix([[1, 2], [3, 4]], "trace")["result"], "5")

    def test_eigenvalues_of_a_diagonal_matrix_are_its_entries(self):
        self.assertEqual(set(symbolic_matrix([[2, 0], [0, 3]], "eigenvalues")["result"]), {"2", "3"})

    def test_singular_matrix_has_no_inverse(self):
        with self.assertRaises(ToolError):
            symbolic_matrix([[1, 2], [2, 4]], "inverse")

    def test_matrix_chapter_operations_have_exact_steps(self):
        self.assertEqual(matrix_arithmetic([[1, 2]], [[3], [4]], "multiply")["result"], "[[11]]")
        step = matrix_row_operation([[1, 2], [3, 4]], "add_multiple", 1, 0, "-3")
        self.assertEqual(step["after"], "[[1, 2], [0, -2]]")
        solution = matrix_linear_system([[2, 1], [1, -1]], [5, 1], "cramer")
        self.assertEqual(solution["solution"], "[[2], [1]]")
        self.assertTrue(matrix_properties([[1, 2], [3, 4]])["cayley_hamilton_verified"])

    def test_determinant_chapter_tools_show_rules_and_geometry(self):
        expansion = determinant_cofactor_expansion([[1, 2], [3, 4]], "row", 0)
        self.assertEqual(expansion["determinant"], "-2")
        effect = determinant_row_effect([[1, 2], [3, 4]], "swap", 0, 1)
        self.assertEqual(effect["after_determinant"], "2")
        solved = determinant_parameter_solve([["a", 1], [2, 3]], "a")
        self.assertEqual(solved["solutions"], ["2/3"])
        self.assertEqual(determinant_signed_area([[1, 0], [0, -2]])["orientation"], "reversed")


class ThreeDGeometryTests(unittest.TestCase):
    def test_line_plane_intersection_and_point_distances(self):
        hit = three_d_line_plane_intersection([0, 0, 0], [1, 1, 1], [1, 1, 1, 3])
        self.assertEqual(hit["relation"], "intersects")
        self.assertEqual(hit["intersection"], ["1", "1", "1"])
        plane_distance = three_d_point_distance([1, 2, 5], plane=[0, 0, 1, 1])
        self.assertEqual(plane_distance["distance"], "4")

    def test_skew_lines_and_plane_relations(self):
        lines = three_d_line_relation([0, 0, 0], [1, 0, 0], [0, 1, 1], [0, 1, 0])
        self.assertEqual(lines["relation"], "skew")
        planes = three_d_plane_relation([1, 0, 0, 0], [0, 1, 0, 0])
        self.assertEqual(planes["relation"], "intersecting")
        built = three_d_plane_from_points([[0, 0, 0], [1, 0, 0], [0, 1, 0]])
        self.assertEqual(built["plane"], ["0", "0", "1", "0"])


class ComplexNumberTests(unittest.TestCase):
    def test_analysis_and_operation_match_argand_geometry(self):
        analysed = complex_number_analysis("3+4*I")
        self.assertEqual(analysed["modulus"], "5")
        self.assertEqual(analysed["conjugate"], "3 - 4*I")
        product = complex_number_operation("1+I", "1-I", "multiply")
        self.assertEqual(product["result"], "2")

    def test_roots_and_locus_tools(self):
        roots = complex_polynomial_roots("z**2+1=0")
        self.assertEqual(roots["count"], 2)
        unity = roots_of_unity(4)
        self.assertEqual(unity["geometry"], "regular 4-gon on the unit circle")
        locus = complex_locus("equidistant", "1+I", "3+I")
        self.assertEqual(locus["locus"], "perpendicular bisector of the segment joining a and b")

    def test_non_square_is_rejected_for_square_only_operations(self):
        with self.assertRaises(ToolError):
            symbolic_matrix([[1, 2, 3], [4, 5, 6]], "determinant")


class VectorCalculusTests(unittest.TestCase):
    def test_gradient_divergence_curl_laplacian(self):
        self.assertEqual(symbolic_vector_calculus(["x**2+y**2"], "gradient", ["x", "y"])["result"], ["2*x", "2*y"])
        self.assertEqual(symbolic_vector_calculus(["x", "y", "z"], "divergence", ["x", "y", "z"])["result"], "3")
        self.assertEqual(symbolic_vector_calculus(["-y", "x", "0"], "curl", ["x", "y", "z"])["result"], ["0", "0", "2"])
        self.assertEqual(symbolic_vector_calculus(["x**2+y**2"], "laplacian", ["x", "y"])["result"], "4")

    def test_curl_of_a_gradient_is_zero(self):
        """A vector identity, so a failure here is a real error rather than a taste."""
        gradient = symbolic_vector_calculus(["x*y*z"], "gradient", ["x", "y", "z"])["result"]
        self.assertEqual(symbolic_vector_calculus(gradient, "curl", ["x", "y", "z"])["result"], ["0", "0", "0"])


class OdeTests(unittest.TestCase):
    def test_solutions_are_substituted_back(self):
        for equation in ("Derivative(y,x) + y", "Derivative(y,x) - 2*y", "Derivative(y,x,2) + y"):
            with self.subTest(equation=equation):
                self.assertTrue(symbolic_ode(equation)["verified"])

    def test_initial_conditions_remove_the_constant(self):
        """y(0) needs the Function class while the equation needs y(x).

        One binding cannot serve both, and using only the applied form made every
        initial-value problem fail with "'y' object is not callable".
        """
        solution = symbolic_ode("Derivative(y,x) + y", initial_conditions={"y(0)": 1})["solutions"][0]
        self.assertIn("exp(-x)", solution)
        self.assertNotIn("C1", solution)

    def test_numeric_integration_of_the_harmonic_oscillator(self):
        """x'=y, y'=-x starting at (1,0) must reach (-1,0) after half a period."""
        final = numeric_ode(["y", "-x"], [1, 0], 0, math.pi, points=60)["final_state"]
        self.assertAlmostEqual(final["x"], -1.0, places=4)
        self.assertAlmostEqual(final["y"], 0.0, places=4)


class OptimizationTests(unittest.TestCase):
    def test_finds_a_known_minimum(self):
        result = numeric_optimize("(x-2)**2 + (y+1)**2", guess=[0, 0])
        self.assertAlmostEqual(result["argument"]["x"], 2.0, places=4)
        self.assertAlmostEqual(result["argument"]["y"], -1.0, places=4)

    def test_polynomial_interpolation_reproduces_a_quadratic(self):
        self.assertAlmostEqual(
            numeric_interpolate([0, 1, 2, 3], [0, 1, 4, 9], [1.5], kind="polynomial")["values"][0], 2.25, places=6
        )


class DiscreteTests(unittest.TestCase):
    def test_exact_integer_facts(self):
        self.assertEqual(number_theory("gcd", [48, 18])["result"], 6)
        self.assertEqual(number_theory("factorize", [360])["result"], {"2": 3, "3": 2, "5": 1})
        self.assertTrue(number_theory("is_prime", [97])["result"])
        self.assertEqual(number_theory("mod_inverse", [3], modulus=11)["result"], 4)

    def test_chinese_remainder(self):
        """x = 2 (mod 3), 3 (mod 5), 2 (mod 7) has the classical answer 23."""
        self.assertEqual(number_theory("crt", [[2, 3], [3, 5], [2, 7]])["result"], 23)

    def test_counting(self):
        self.assertEqual(combinatorics("combinations", 10, 3)["result"], 120)
        self.assertEqual(combinatorics("permutations", 5, 2)["result"], 20)
        self.assertEqual(combinatorics("catalan", 5)["result"], 42)

    def test_modus_ponens_is_a_tautology(self):
        """Parenthesised deliberately: Python binds >> tighter than &, so
        "(p >> q) & p >> q" is "(p>>q) & (p>>q)" and proves nothing."""
        self.assertTrue(logic_table("((p >> q) & p) >> q")["tautology"])
        self.assertTrue(logic_table("p & ~p")["contradiction"])

    def test_graph_paths_and_spanning_trees(self):
        edges = [["a", "b", 1], ["b", "c", 2], ["a", "c", 5]]
        shortest = graph_algorithm(edges, "shortest_path", source="a", target="c")["result"]
        self.assertEqual(shortest["path"], ["a", "b", "c"])
        self.assertEqual(shortest["length"], 3.0)
        self.assertEqual(graph_algorithm(edges, "minimum_spanning_tree")["result"]["weight"], 3.0)

    def test_even_cycle_is_bipartite_and_odd_is_not(self):
        square = [["a", "b"], ["b", "c"], ["c", "d"], ["d", "a"]]
        triangle = [["a", "b"], ["b", "c"], ["c", "a"]]
        self.assertTrue(graph_algorithm(square, "is_bipartite")["result"])
        self.assertFalse(graph_algorithm(triangle, "is_bipartite")["result"])


class StatisticsTests(unittest.TestCase):
    def test_distribution_moments_match_theory(self):
        self.assertAlmostEqual(probability("normal", [0, 1])["mean"], 0.0)
        self.assertAlmostEqual(probability("binomial", [10, 0.5])["mean"], 5.0)
        self.assertAlmostEqual(probability("binomial", [10, 0.5])["variance"], 2.5)
        self.assertAlmostEqual(probability("exponential", [2])["variance"], 0.25)
        self.assertAlmostEqual(probability("poisson", [3])["variance"], 3.0)

    def test_standard_normal_is_symmetric_about_zero(self):
        self.assertAlmostEqual(probability("normal", [0, 1], query="cdf", at=0)["cdf"], 0.5, places=8)

    def test_perfect_line_has_r_squared_one(self):
        fit = linear_regression([1, 2, 3, 4], [2, 4, 6, 8])
        self.assertAlmostEqual(fit["slope"], 2.0)
        self.assertAlmostEqual(fit["r_squared"], 1.0)

    def test_sample_summary(self):
        self.assertAlmostEqual(statistics_summary([1, 2, 3, 4, 5])["mean"], 3.0)

    def test_monte_carlo_converges_to_the_analytic_expectation(self):
        """E[x^2] for x ~ U(0,1) is 1/3."""
        estimate = monte_carlo("x**2", samples=200_000)["estimate"]
        self.assertLess(abs(estimate - 1 / 3), 0.01)


class GeometryTests(unittest.TestCase):
    def test_three_four_five_triangle(self):
        result = geometry_solve("triangle_properties", [[0, 0], [3, 0], [0, 4]])
        self.assertEqual(result["area"], "6")
        self.assertTrue(result["is_right"])
        self.assertEqual(round(result["angle_sum"]), 180)

    def test_distance_and_intersection(self):
        self.assertAlmostEqual(geometry_solve("distance", [[0, 0], [3, 4]])["decimal"], 5.0)
        self.assertEqual(geometry_solve("intersection", [[0, 0], [2, 2], [0, 2], [2, 0]])["decimal"], [1.0, 1.0])

    def test_parallel_lines_do_not_meet(self):
        result = geometry_solve("intersection", [[0, 0], [1, 0], [0, 1], [1, 1]])
        self.assertIsNone(result["result"])

    def test_circle_through_three_points_on_the_unit_circle(self):
        self.assertEqual(geometry_solve("circle_through", [[1, 0], [0, 1], [-1, 0]])["radius"], "1")

    def test_collinear_points_form_no_triangle(self):
        self.assertTrue(geometry_solve("collinear", [[0, 0], [1, 1], [2, 2]])["collinear"])
        with self.assertRaises(ToolError):
            geometry_solve("triangle_properties", [[0, 0], [1, 1], [2, 2]])

    def test_ellipse_eccentricity(self):
        self.assertAlmostEqual(conic_properties("ellipse", [5, 3])["eccentricity"], 0.8)


class CompetitiveExamTests(unittest.TestCase):
    def test_router_requires_a_diagram_and_checked_tools_for_mechanics(self):
        requirements = competitive_exam_requirements("A projectile is fired from a cliff. Find its range.")
        self.assertIn("mechanics", requirements["matched_domains"])
        self.assertIn("jee_mechanics", requirements["required_tools"])
        self.assertIn("labelled diagram or graph before the derivation", requirements["required_solution_structure"])

    def test_braking_and_projectile_results(self):
        braking = jee_mechanics("uniform_acceleration", initial_velocity=20, final_velocity=0, time=4)
        self.assertAlmostEqual(braking["acceleration"], -5)
        self.assertAlmostEqual(braking["distance"], 40)
        projectile = jee_mechanics("projectile", speed=20, angle_deg=30, gravity=10)
        self.assertAlmostEqual(projectile["time_of_flight"], 2)
        self.assertAlmostEqual(projectile["range"], 20 * math.sqrt(3), places=7)

    def test_kepler_small_radial_period_matches_derived_formula(self):
        result = jee_mechanics("small_radial_kepler", mass=2, force_constant=8, radius=2)
        self.assertAlmostEqual(result["angular_frequency_squared"], 0.5)
        self.assertAlmostEqual(result["period"], 2 * math.pi * math.sqrt(2))
        self.assertAlmostEqual(result["period"], result["period_from_l"])

    def test_meter_scale_alternating_friction_switches(self):
        result = meter_scale_alternating_friction(0, 90, 0.40, 0.32)
        self.assertAlmostEqual(result["left_position_at_first_switch_cm"], 18.0)
        self.assertAlmostEqual(result["x_right_from_center_cm"], 25.6)

    def test_rotation_centre_of_mass_and_orbit(self):
        rotation = rigid_body_rotation("disc", mass_kg=2, radius_m=1, torque_nm=4)
        self.assertAlmostEqual(rotation["moment_of_inertia_kg_m2"], 1.0)
        self.assertAlmostEqual(rotation["angular_acceleration_rad_per_s2"], 4.0)
        centre = centre_of_mass([1, 3], [[0, 0], [4, 0]])
        self.assertEqual(centre["centre_of_mass_m"], [3.0, 0.0])
        orbit = gravitation_orbit(1, 5.972e24, 6.371e6)
        self.assertAlmostEqual(orbit["escape_speed_m_per_s"], math.sqrt(2) * orbit["orbital_speed_m_per_s"])

    def test_damping_terminal_velocity_and_decay(self):
        oscillator = damped_oscillator(mass_kg=1, stiffness_n_per_m=4, damping_kg_per_s=2)
        self.assertEqual(oscillator["regime"], "underdamped")
        self.assertAlmostEqual(oscillator["damped_angular_frequency"], math.sqrt(3))
        falling = terminal_velocity_sphere(0.001, 2000, 1000, 1, gravity=10)
        self.assertEqual(falling["direction"], "downward")
        self.assertAlmostEqual(falling["terminal_velocity_m_per_s"], 2 / 900)
        decay = radioactive_decay(100, half_life_s=10, time_s=10)
        self.assertAlmostEqual(decay["remaining_nuclei"], 50.0)
        self.assertAlmostEqual(decay["decayed_fraction"], 0.5)

    def test_extended_jee_physics_tools_match_known_results(self):
        wire = elasticity_wire(100, 2, 1e-4, 2e11)
        self.assertAlmostEqual(wire["extension_m"], 1e-5)
        capillary = surface_tension_capillary(0.072, 0.001, 0, 1000, gravity=10)
        self.assertAlmostEqual(capillary["height_m"], 0.0144)
        mixture = calorimetry_mix([1, 1], [1000, 1000], [300, 400])
        self.assertAlmostEqual(mixture["equilibrium_temperature_k"], 350)
        self.assertAlmostEqual(doppler_effect(1000, 340, observer_speed_m_per_s=34)["observed_frequency_hz"], 1100)
        self.assertAlmostEqual(ray_optics(0.1, 0.3)["image_distance_m"], 0.15)
        self.assertEqual(photoelectric_effect(2, 1.9)["emission"], False)
        self.assertAlmostEqual(photoelectric_effect(2, 5)["stopping_potential_v"], 3)
        self.assertAlmostEqual(semiconductor_diode(5, 100)["current_a"], 0.043)
        self.assertAlmostEqual(heat_conduction(2, 1, 400, 300, 0.5)["heat_flow_rate_w"], 400)
        self.assertAlmostEqual(rlc_resonance(10, 1, 0.25, 20)["resonant_frequency_hz"], 1 / math.pi)
        self.assertAlmostEqual(polarization_malus(100, 60)["transmitted_intensity"], 25)

    def test_core_physical_chemistry_tools(self):
        reaction = stoichiometry_limit([2, 5], [1, 2], product_coefficient=2, product_molar_mass=18)
        self.assertEqual(reaction["limiting_reactant_indices"], [0])
        self.assertAlmostEqual(reaction["product_moles"], 4)
        self.assertAlmostEqual(reaction["product_mass_g"], 72)
        gas = ideal_gas_state(101325, 0.024465, 1, 298.15)
        self.assertLess(gas["relative_residual"], 0.01)
        acid = weak_acid_ph(0.1, 1e-5)
        self.assertAlmostEqual(acid["ph"], 3.0, places=2)

    def test_transformer_transmission_ratio_and_loss_reduction(self):
        result = power_transmission(600, 4000, 0.1, 200)
        self.assertAlmostEqual(result["plant_current_a"], 150)
        self.assertAlmostEqual(result["transmission_voltage_v"], 40000)
        self.assertAlmostEqual(result["line_current_a"], 15)
        self.assertEqual(result["step_down_ratio"], "200:1")
        self.assertAlmostEqual(result["line_loss_reduction_factor"], 100)

    def test_linear_drag_projectile_matches_the_given_wall_distance(self):
        result = linear_drag_projectile(0.2, 0.1, 270, 60, 2, e_approx=2.7)
        self.assertAlmostEqual(result["beta_per_s"], 0.5)
        self.assertAlmostEqual(result["position_at_time_m"]["x"], 170.0, places=6)

    def test_full_pcm_catalogue_exposes_coverage_and_database_gaps(self):
        catalogue = competitive_exam_catalogue()
        self.assertIn("physics_electricity_magnetism", catalogue["domains"])
        self.assertIn("chemistry_organic", catalogue["known_gaps"])
        self.assertIn("math_algebra_calculus", catalogue["domains"])

    def test_electricity_tools_match_known_networks_and_coulomb_law(self):
        series = circuit_network([2, 3], 10, "series")
        self.assertAlmostEqual(series["total_current_a"], 2)
        self.assertAlmostEqual(series["total_power_w"], 20)
        parallel = capacitor_network([2e-6, 3e-6], 10, "parallel")
        self.assertAlmostEqual(parallel["equivalent_capacitance_f"], 5e-6)
        field = electrostatics_point_charges([[1e-6, 0, 0]], [1, 0])
        self.assertAlmostEqual(field["field_magnitude_n_per_c"], 8.9875517923e3, places=4)

    def test_thermal_modern_and_equilibrium_tools(self):
        process = thermodynamic_process(1, 300, 400, "isobaric")
        self.assertAlmostEqual(process["work_by_gas_j"], 831.4462618, places=4)
        self.assertAlmostEqual(process["heat_added_j"], process["delta_u_j"] + process["work_by_gas_j"])
        lyman = hydrogen_transition(2, 1)
        self.assertEqual(lyman["kind"], "emission")
        self.assertAlmostEqual(lyman["wavelength_nm"], 121.55, places=1)
        self.assertEqual(chemical_equilibrium_direction(0.1, 1)["direction"], "forward, toward products")

    def test_advanced_visual_topics_have_checked_tools(self):
        self.assertAlmostEqual(ac_phasor_analysis(100, 5, 60)["real_power_w"], 250)
        self.assertAlmostEqual(electromagnetic_induction(100, 0.1, 0.3, 2)["induced_emf_v"], -10)
        self.assertAlmostEqual(wave_optics("double_slit", 600, 2, 0.5)["distance_mm"], 2.4)
        self.assertAlmostEqual(fluid_flow_bernoulli(2, 1, 3, 100000)["speed_2_m_per_s"], 6)
        self.assertEqual(organic_reference_lookup("sn2")["product_prediction_allowed"], False)
        self.assertEqual(coordination_complex_analysis(6, 5)["geometry"], "octahedral")
        self.assertTrue(vector_plane_relation([1, -1, 0], [1, 1, 0, 0])["parallel_to_plane"])


class CreatorToolTests(unittest.TestCase):
    def test_calculus_brief_requests_continuous_visual_motion(self):
        brief = study_animation_brief("Visualise the derivative of a function")
        primitives = {item["primitive"] for item in brief["motion_primitives"]}
        self.assertIn("continuous_parameter", primitives)
        self.assertIn("traced_motion", primitives)
        self.assertIn("do not use decorative motion or equations moving without explanatory purpose", brief["required_visual_rules"])

    def test_timing_and_motion_audit_protect_readability(self):
        timing = study_animation_timing(6, "worked_problem")
        self.assertGreater(timing["recommended_seconds"], 45)
        audit = motion_design_audit([
            {"primitive": "path_follow", "purpose": "show the bicycle position changing with time"},
            {"primitive": "spin", "purpose": ""},
        ])
        self.assertFalse(audit["approved"])


class ChapterExpertRegistryTests(unittest.TestCase):
    def test_every_pcm_chapter_is_individually_profiled(self):
        report = jee_chapter_coverage()
        self.assertGreaterEqual(report["total"], 100)
        self.assertTrue({"physics", "chemistry", "mathematics"} <= report["by_subject"].keys())
        self.assertEqual(report["readiness"]["planned"], 0)
        self.assertEqual(report["readiness"]["infrastructure_ready"], report["total"])
        expert = jee_chapter_expert("electromagnetic induction")
        self.assertTrue(expert["solver_or_reference"])
        self.assertTrue(expert["verification"])
        self.assertTrue(expert["visuals"])
        self.assertEqual(expert["syllabus_sources"], ["jee_advanced_2026", "jee_main_2026"])
        self.assertTrue(expert["representative_test_required"])
        self.assertEqual(expert["evidence"]["tool_test"], "passed")
        self.assertIsNone(expert["evidence"]["render_review"])
        self.assertTrue(all(not chapter["missing_verification"] for chapter in report["chapters"].values()))

    def test_every_chapter_has_a_passing_known_answer_case(self):
        self.assertEqual(set(CHAPTER_CASES), set(jee_chapter_coverage()["chapters"]))
        for identifier in CHAPTER_CASES:
            with self.subTest(chapter=identifier):
                profile = jee_chapter_expert(identifier)
                self.assertIn(CHAPTER_CASES[identifier]["tool"], profile["solver_or_reference"])
                self.assertTrue(CHAPTER_CASES[identifier]["expected"])
                self.assertNotEqual(
                    CHAPTER_CASES[identifier]["prompt"],
                    f"Representative known-answer check for {identifier.replace('_', ' ')}.",
                )
                self.assertTrue(execute_case(identifier)["passed"])
        self.assertTrue(jee_chapter_case("ray optics", execute=True)["passed"])


if __name__ == "__main__":
    unittest.main()
