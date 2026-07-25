import unittest

from agents.intent_agent import run_intent_agent
from agents.math_planner import run_math_planner
from agents.math_verifier import run_math_verifier
from agents.tool_router import select_tools
from tools.numerical_math import gradient_descent_sequence


class PipelineTests(unittest.TestCase):
    def test_gradient_descent_plan_is_verified(self):
        intent = run_intent_agent("Explain gradient descent visually for a beginner")
        plan = run_math_planner(intent)
        verified = run_math_verifier(plan)
        self.assertEqual(intent.topic, "gradient descent")
        self.assertTrue(verified["valid"])
        self.assertIn("sympy_verify", select_tools(intent, plan.model_dump()))

    def test_gradient_descent_moves_to_minimum(self):
        values = gradient_descent_sequence(-2, 0.2, 8, lambda x: 2 * (x - 2))
        self.assertLess(abs(values[-1] - 2), abs(values[0] - 2))


if __name__ == "__main__":
    unittest.main()
