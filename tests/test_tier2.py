"""Tier 2 compute tools, checked against results known independently.

Every assertion here has an answer that can be looked up or derived by hand.
That is the point: a wrapper that returns something plausible is worth nothing,
and only a known answer distinguishes the two.
"""

from __future__ import annotations

import math
import unittest

import sympy as sp

from proofmotion.runtime.registry import ToolError
from proofmotion.tools.algebra import symbolic_algebra, symbolic_matrix, symbolic_vector_calculus
from proofmotion.tools.analysis import numeric_interpolate, numeric_ode, numeric_optimize, symbolic_ode
from proofmotion.tools.competitive import (
    capacitor_network,
    chemical_equilibrium_direction,
    circuit_network,
    competitive_exam_catalogue,
    competitive_exam_requirements,
    electrostatics_point_charges,
    hydrogen_transition,
    ideal_gas_state,
    jee_mechanics,
    power_transmission,
    stoichiometry_limit,
    thermodynamic_process,
    weak_acid_ph,
)
from proofmotion.tools.creator import motion_design_audit, study_animation_brief, study_animation_timing
from proofmotion.tools.discrete import combinatorics, graph_algorithm, logic_table, number_theory
from proofmotion.tools.geometry import conic_properties, geometry_solve
from proofmotion.tools.statistics import linear_regression, monte_carlo, probability, statistics_summary


def equivalent(left: str, right: str) -> bool:
    return sp.simplify(sp.sympify(left) - sp.sympify(right)) == 0


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


if __name__ == "__main__":
    unittest.main()
