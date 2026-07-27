from __future__ import annotations

import unittest

from proofmotion.knowledge.answer_oracle import audit_final_answer, lookup_reference_answer

METER_PROMPT = """Put a uniform meter scale horizontally on your extended index fingers with the left one at 0.00 cm and the right one at 90.00 cm. If the coefficients of static and dynamic friction are 0.40 and 0.32, find xR."""


class AnswerOracleTests(unittest.TestCase):
    def test_only_exact_problem_fingerprint_gets_a_reference(self):
        result = lookup_reference_answer(METER_PROMPT)
        self.assertTrue(result["available"])
        self.assertEqual(result["reference"]["id"], "meter_scale_alternating_friction")
        self.assertFalse(lookup_reference_answer("A meter scale has friction. Find xR.")["available"])

    def test_accepts_formatting_only_numeric_difference(self):
        result = audit_final_answer(METER_PROMPT, r"x_R = 25.6\,\mathrm{cm}")
        self.assertTrue(result["matched"])
        self.assertEqual(result["status"], "matched")

    def test_reports_a_conflicting_final_answer(self):
        result = audit_final_answer(METER_PROMPT, r"x_R = 20\,\mathrm{cm}")
        self.assertFalse(result["matched"])
        self.assertEqual(result["status"], "mismatch")
        self.assertIn("source", result["reference"])

    def test_unknown_question_does_not_change_the_existing_path(self):
        result = audit_final_answer("Find the acceleration of a falling object.", r"a=g")
        self.assertEqual(result["status"], "no_reference")
        self.assertIsNone(result["matched"])

    def test_a_reference_record_keeps_its_context_and_source_kind(self):
        result = lookup_reference_answer(METER_PROMPT)
        reference = result["reference"]
        self.assertEqual(reference["source_kind"], "user_verified")
        self.assertTrue(reference["match_terms"])
