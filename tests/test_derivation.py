"""The shared derivation steps: one copy of the gates, guarding both callers.

The studio's trimmed copy of the pipeline silently lost the completeness retry
and the final-answer gate. These tests hold the gates where both the pipeline
and the studio now get them.

No API key required.
"""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from proofmotion.compose.derivation import IncompletePlan, planned, storyboarded

INTENT = SimpleNamespace(topic="a ramp", domain="physics")
PLAN = SimpleNamespace(final_answer_latex="42", final_answer_explanation="because")


class TestPlanned(unittest.TestCase):
    def test_an_incomplete_plan_is_retried_with_the_problems_attached(self):
        calls = []

        def fake_plan(client, intent, *, exam_requirements=None, completion_feedback=None):
            calls.append(completion_feedback)
            return PLAN

        verdicts = iter([
            {"complete": False, "problems": ["no final answer"]},
            {"complete": True, "problems": []},
        ])
        with (
            patch("proofmotion.agents.planner.plan_mathematics", side_effect=fake_plan),
            patch("proofmotion.agents.completeness.check_solution_completeness",
                  side_effect=lambda plan, intent: next(verdicts)),
        ):
            out = planned(None, INTENT)
        self.assertIs(out, PLAN)
        self.assertEqual(calls, [None, "no final answer"])

    def test_two_incomplete_plans_raise_rather_than_shipping(self):
        with (
            patch("proofmotion.agents.planner.plan_mathematics", return_value=PLAN),
            patch("proofmotion.agents.completeness.check_solution_completeness",
                  return_value={"complete": False, "problems": ["still no answer"]}),
        ):
            with self.assertRaises(IncompletePlan) as caught:
                planned(None, INTENT)
        self.assertIn("still no answer", str(caught.exception))

    def test_the_gate_can_be_stood_down_explicitly(self):
        with (
            patch("proofmotion.agents.planner.plan_mathematics", return_value=PLAN),
            patch("proofmotion.agents.completeness.check_solution_completeness") as check,
        ):
            planned(None, INTENT, require_complete=False)
        check.assert_not_called()


class TestStoryboarded(unittest.TestCase):
    def test_a_deck_that_never_states_its_answer_gets_it_added(self):
        board, repaired = SimpleNamespace(scenes=[]), SimpleNamespace(scenes=["final"])
        verdicts = iter([
            {"complete": False, "problems": ["no FINAL ANSWER scene"]},
            {"complete": True, "problems": []},
        ])
        with (
            patch("proofmotion.agents.director.direct_storyboard", return_value=board),
            patch("proofmotion.agents.completeness.check_storyboard_final_answer",
                  side_effect=lambda storyboard, latex: next(verdicts)),
            patch("proofmotion.agents.completeness.ensure_storyboard_final_answer",
                  return_value=repaired) as ensure,
        ):
            out = storyboarded(None, INTENT, PLAN, {})
        self.assertIs(out, repaired)
        ensure.assert_called_once_with(board, "42", "because")


if __name__ == "__main__":
    unittest.main()
