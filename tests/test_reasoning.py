"""Tier 1 verification tools.

These decide whether a result is *right*, so their own correctness is checked
against physics and mathematics that is known independently — not against
recorded output.
"""

from __future__ import annotations

import unittest

from proofmotion.runtime.registry import ToolError
from proofmotion.tools.reasoning import (
    assumption_check,
    counterexample_search,
    induction_check,
    limiting_case_check,
    plausibility_check,
    symmetry_check,
    units_check,
)


class UnitsTests(unittest.TestCase):
    CORRECT = [
        ("F", "m*a", {"F": "force", "m": "mass", "a": "acceleration"}),
        ("E", "m*c**2", {"E": "energy", "m": "mass", "c": "velocity"}),
        ("E", "m*v**2/2", {"E": "energy", "m": "mass", "v": "velocity"}),
        ("P", "F*v", {"P": "power", "F": "force", "v": "velocity"}),
        ("V", "I*R", {"V": "voltage", "I": "current", "R": "impedance"}),
        ("T", "2*pi*sqrt(L/g)", {"T": "time", "L": "length", "g": "acceleration"}),
        ("N", "m*v**2/r", {"N": "force", "m": "mass", "v": "velocity", "r": "length"}),
    ]
    WRONG = [
        ("F", "m*v", {"F": "force", "m": "mass", "v": "velocity"}),
        ("E", "m*c", {"E": "energy", "m": "mass", "c": "velocity"}),
        ("V", "I*R**2", {"V": "voltage", "I": "current", "R": "impedance"}),
    ]

    def test_accepts_correct_physics(self):
        for left, right, dims in self.CORRECT:
            with self.subTest(claim=f"{left}={right}"):
                self.assertTrue(units_check(left, right, dims)["consistent"])

    def test_rejects_wrong_physics(self):
        for left, right, dims in self.WRONG:
            with self.subTest(claim=f"{left}={right}"):
                self.assertFalse(units_check(left, right, dims)["consistent"])

    def test_symbols_sympy_reserves_are_still_usable(self):
        """E is Euler's number and I the imaginary unit in sympy.

        Physics writes both constantly. Before local symbols were forced,
        "E = m*c**2" arrived with no free symbols and measured as dimensionless.
        """
        report = units_check("E", "m*c**2", {"E": "energy", "m": "mass", "c": "velocity"})
        self.assertTrue(report["consistent"])
        self.assertNotEqual(report["left_dimension"], "dimensionless")

    def test_unknown_dimension_names_are_rejected_with_the_list(self):
        with self.assertRaises(ToolError) as caught:
            units_check("F", "m*a", {"F": "sproing", "m": "mass", "a": "acceleration"})
        self.assertIn("force", str(caught.exception))


class CounterexampleTests(unittest.TestCase):
    def test_refutes_a_false_identity_with_a_witness(self):
        result = counterexample_search("(x+1)**2 = x**2 + 1")
        self.assertTrue(result["refuted"])
        self.assertIn("x", result["counterexample"])

    def test_refutes_a_false_inequality(self):
        self.assertTrue(counterexample_search("x**2 >= x")["refuted"])

    def test_survives_a_true_identity_without_claiming_proof(self):
        result = counterexample_search("(x+1)**2 = x**2 + 2*x + 1")
        self.assertFalse(result["refuted"])
        self.assertIn("not proof", result["verdict"])

    def test_a_claim_with_no_relation_is_an_error(self):
        with self.assertRaises(ToolError):
            counterexample_search("x**2 + 1")


class LimitingCaseTests(unittest.TestCase):
    def test_confirms_a_correct_limit(self):
        self.assertTrue(limiting_case_check("sin(x)/x", "x", "0", "1")["matches"])

    def test_flags_a_wrong_limit(self):
        self.assertFalse(limiting_case_check("sin(x)/x", "x", "0", "0")["matches"])

    def test_relativistic_energy_reduces_to_classical(self):
        """A real limiting-case check: gamma -> 1 as v -> 0."""
        self.assertTrue(limiting_case_check("1/sqrt(1 - v**2/c**2)", "v", "0", "1")["matches"])


class PlausibilityTests(unittest.TestCase):
    def test_accepts_a_positive_kinetic_energy(self):
        self.assertTrue(plausibility_check("m*v**2/2", {"m": 2, "v": 3}, expect_sign="positive")["plausible"])

    def test_rejects_a_negative_energy(self):
        self.assertFalse(plausibility_check("-m*v**2/2", {"m": 2, "v": 3}, expect_sign="positive")["plausible"])

    def test_rejects_a_value_above_a_stated_maximum(self):
        result = plausibility_check("v", {"v": 4e8}, maximum=3e8)
        self.assertFalse(result["plausible"])

    def test_missing_values_raise_rather_than_defaulting(self):
        with self.assertRaises(ToolError):
            plausibility_check("m*v**2/2", {"m": 2})


class AssumptionTests(unittest.TestCase):
    def test_all_conditions_holding(self):
        self.assertTrue(assumption_check(["eta > 0", "eta < 2/L"], {"eta": 0.5, "L": 2})["all_hold"])

    def test_names_the_violated_condition(self):
        """This is what tells an interactive slider where the theorem stops."""
        result = assumption_check(["eta > 0", "eta < 2/L"], {"eta": 1.5, "L": 2})
        self.assertFalse(result["all_hold"])
        self.assertEqual(result["violated"], ["eta < 2/L"])

    def test_handles_a_non_equality_condition(self):
        self.assertTrue(assumption_check(["x != 0"], {"x": 3})["all_hold"])
        self.assertFalse(assumption_check(["x != 0"], {"x": 0})["all_hold"])


class InductionTests(unittest.TestCase):
    def test_confirms_the_triangular_number_formula(self):
        result = induction_check("Sum(k,(k,1,n)) = n*(n+1)/2")
        self.assertTrue(result["holds_for_all_tested"])
        self.assertIn("inductive step still needs a proof", result["verdict"])

    def test_finds_the_first_failing_case(self):
        result = induction_check("Sum(k,(k,1,n)) = n*n/2")
        self.assertFalse(result["holds_for_all_tested"])
        self.assertEqual(result["failures"][0]["n"], 1)


class SymmetryTests(unittest.TestCase):
    def test_even_function_is_invariant(self):
        self.assertTrue(symmetry_check("x**2", {"x": "-x"})["satisfied"])

    def test_odd_function_is_antisymmetric_not_invariant(self):
        self.assertTrue(symmetry_check("x**3", {"x": "-x"}, expect="antisymmetric")["satisfied"])
        self.assertFalse(symmetry_check("x**3", {"x": "-x"})["satisfied"])

    def test_exchange_symmetry_between_two_bodies(self):
        """Gravitational force is symmetric under swapping the masses."""
        self.assertTrue(symmetry_check("G*m1*m2/r**2", {"m1": "m2", "m2": "m1"})["satisfied"])


class VerifierIntegrationTests(unittest.TestCase):
    """The bridge from LaTeX to sympy decides how much can be checked at all."""

    def test_notation_with_implicit_multiplication_is_checkable(self):
        """Mathematics writes 2x; Python demands 2*x.

        Before implicit multiplication was restored, a true identity came back
        "not mechanically checkable" — the conversion was the obstacle, not the
        mathematics, and a whole plan could pass while proving nothing.
        """
        from proofmotion.agents.verifier import verify_plan
        from schemas.math_plan import MathematicalPlan, MathStep

        claims = [
            ("(x+1)^2 = x^2+2x+1", True),
            ("(x+1)^2 = x^2+1", False),
            (r"\sin^2 x + \cos^2 x = 1", True),
            ("2x + 3x = 5x", True),
            ("(a+b)(a-b) = a^2 - b^2", True),
            ("x^2 - 1 = (x-1)(x+2)", False),
        ]
        plan = MathematicalPlan(
            topic="identities",
            concept_sequence=[
                MathStep(index=i + 1, concept="c", equation_latex=latex, explanation="")
                for i, (latex, _) in enumerate(claims)
            ],
        )
        report = verify_plan(plan)
        for check, (latex, expected) in zip(report["checks"], claims, strict=True):
            with self.subTest(claim=latex):
                self.assertEqual(check.get("equal"), expected, check)


if __name__ == "__main__":
    unittest.main()
