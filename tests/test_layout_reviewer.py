from __future__ import annotations

import unittest
from unittest.mock import patch

from proofmotion.agents.layout_reviewer import text_layout_issue_count, validate_and_repair_text_layout

BAD = {"ok": False, "text_overlaps": [{"between": ["a", "b"]}], "out_of_frame": [], "unreadable_text": [], "text_on_ink": []}
CLEAN = {"ok": True, "text_overlaps": [], "out_of_frame": [], "unreadable_text": [], "text_on_ink": []}


class LayoutReviewerTests(unittest.TestCase):
    def test_counts_text_issues_including_text_on_ink(self):
        report = {**BAD, "text_on_ink": [{"text": "x"}], "unreadable_text": [{"label": "tiny"}]}
        self.assertEqual(text_layout_issue_count(report), 3)

    @patch("proofmotion.agents.layout_reviewer.manim_validate_code", return_value={"valid": True})
    @patch("proofmotion.agents.layout_reviewer.polish_scene", return_value={"code": "clean"})
    @patch("proofmotion.agents.layout_reviewer.inspect_scene", side_effect=[BAD, CLEAN])
    def test_repairs_until_measured_text_is_clean(self, inspect, polish, validate):
        result = validate_and_repair_text_layout(object(), "bad")
        self.assertTrue(result["ok"])
        self.assertEqual(result["code"], "clean")
        self.assertEqual(result["attempts"], 1)

    @patch("proofmotion.agents.layout_reviewer.manim_validate_code", return_value={"valid": True})
    @patch("proofmotion.agents.layout_reviewer.polish_scene", return_value={"code": "not_better"})
    @patch("proofmotion.agents.layout_reviewer.inspect_scene", side_effect=[BAD, BAD])
    def test_blocks_when_repair_does_not_clear_overlap(self, inspect, polish, validate):
        result = validate_and_repair_text_layout(object(), "bad")
        self.assertFalse(result["ok"])
        self.assertEqual(result["report"], BAD)

    @patch("proofmotion.agents.layout_reviewer.manim_validate_code", return_value={"valid": True})
    @patch("proofmotion.agents.layout_reviewer.polish_scene_direct", return_value={"code": "clean"})
    @patch("proofmotion.agents.layout_reviewer.inspect_scene", side_effect=[
        {"ok": False, "text_overlaps": [], "out_of_frame": [{"label": "caption"}], "unreadable_text": [], "text_on_ink": []},
        CLEAN,
    ])
    def test_single_out_of_frame_caption_uses_direct_repair(self, inspect, direct, validate):
        result = validate_and_repair_text_layout(object(), "bad")

        self.assertTrue(result["ok"])
        direct.assert_called_once()

    @patch("proofmotion.agents.debugger.run_agent")
    def test_polisher_receives_the_specific_text_on_ink_collision(self, run_agent):
        from types import SimpleNamespace

        from proofmotion.agents.debugger import polish_scene

        run_agent.return_value = SimpleNamespace(content="from manim import *\nclass GeneratedScene(Scene): pass", tools_used=[])
        report = {**BAD, "text_on_ink": [{"beat": 3, "text": "MathTex(A)", "over": "Line", "severity": "major"}]}
        polish_scene(object(), "from manim import *\nclass GeneratedScene(Scene): pass", report, max_iterations=1)
        prompt = run_agent.call_args.args[2]
        self.assertIn('"text_on_ink"', prompt)
        self.assertIn("MathTex(A)", prompt)
