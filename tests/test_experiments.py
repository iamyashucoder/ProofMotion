from __future__ import annotations

import unittest

from proofmotion.tools.experiments import (
    measurement_line_fit,
    proof_obligations,
    propagate_measurement_uncertainty,
)


class ExperimentAndProofToolTests(unittest.TestCase):
    def test_line_fit_exposes_slope_and_residual_evidence(self):
        result = measurement_line_fit([0, 1, 2, 3], [1, 3, 5, 7], "extension", "force")
        self.assertAlmostEqual(result["slope"], 2.0)
        self.assertAlmostEqual(result["intercept"], 1.0)
        self.assertAlmostEqual(result["r_squared"], 1.0)
        self.assertEqual(len(result["points"]), 4)

    def test_uncertainty_propagation_uses_symbolic_derivatives(self):
        result = propagate_measurement_uncertainty("v/t", {"v": 10, "t": 2}, {"v": 0.2, "t": 0.1})
        self.assertAlmostEqual(result["value"], 5.0)
        self.assertGreater(result["absolute_uncertainty"], 0)

    def test_induction_tool_requires_all_core_obligations(self):
        result = proof_obligations("sum(k, 1, n) = n*(n+1)/2", "induction", ["n is a positive integer"])
        text = " ".join(result["obligations"])
        self.assertIn("base case", text)
        self.assertIn("k -> k+1", text)
