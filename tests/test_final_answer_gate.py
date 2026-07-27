from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from proofmotion.pipeline import validate_and_repair_final_answer
from schemas.intent import AnimationIntent
from schemas.math_plan import MathematicalPlan, MathStep

PROMPT = """Put a uniform meter scale horizontally on your extended index fingers with the left one at 0.00 cm and the right one at 90.00 cm. If the coefficients of static and dynamic friction are 0.40 and 0.32, find xR."""


def plan(answer: str) -> MathematicalPlan:
    return MathematicalPlan(
        topic="meter scale", final_answer_latex=answer, final_answer_explanation="answer",
        concept_sequence=[MathStep(index=1, concept="balance", equation_latex=answer, explanation="derive")],
    )


class FinalAnswerGateTests(unittest.TestCase):
    def setUp(self):
        self.intent = AnimationIntent(topic="meter scale", domain="mechanics", educational_goal="solve", difficulty="advanced")

    def test_matching_valid_context_is_confirmed(self):
        result, audit = validate_and_repair_final_answer(Mock(), self.intent, PROMPT, plan(r"x_R=25.6\,\mathrm{cm}"), None)
        self.assertEqual(result.final_answer_latex, r"x_R=25.6\,\mathrm{cm}")
        self.assertEqual(audit["outcome"], "confirmed")

    @patch("proofmotion.pipeline.plan_mathematics")
    def test_mismatch_is_repaired_then_confirmed(self, planner):
        planner.return_value = plan(r"x_R=25.60\,\mathrm{cm}")
        result, audit = validate_and_repair_final_answer(Mock(), self.intent, PROMPT, plan(r"x_R=20\,\mathrm{cm}"), None)
        self.assertEqual(result.final_answer_latex, r"x_R=25.60\,\mathrm{cm}")
        self.assertEqual(audit["outcome"], "repaired_and_confirmed")
        self.assertEqual(planner.call_count, 1)

    @patch("proofmotion.pipeline.plan_mathematics")
    def test_unrepaired_mismatch_is_blocked(self, planner):
        planner.return_value = plan(r"x_R=20\,\mathrm{cm}")
        _, audit = validate_and_repair_final_answer(Mock(), self.intent, PROMPT, plan(r"x_R=19\,\mathrm{cm}"), None)
        self.assertEqual(audit["outcome"], "mismatch_blocked")
