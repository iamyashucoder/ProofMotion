from __future__ import annotations

import unittest

from proofmotion.tools.cinematic import cinematic_chase_brief, non_graphic_action_audit, vehicle_motion_profile


class CinematicToolTests(unittest.TestCase):
    def test_chase_brief_has_safe_cinematic_beats(self):
        brief = cinematic_chase_brief(36, 24)
        self.assertEqual(brief["render"]["resolution"], "1920x1080")
        self.assertEqual(len(brief["shots"]), 5)
        self.assertIn("no blood, wounds, or body impact close-ups", brief["safety"])

    def test_vehicle_profile_has_believable_noninstant_braking(self):
        result = vehicle_motion_profile(20, 5, 0.5, "loose_gravel")
        self.assertAlmostEqual(result["braking_time_seconds"], 4.0)
        self.assertAlmostEqual(result["total_stopping_distance_m"], 50.0)
        self.assertEqual(result["surface_traction"], "low")

    def test_safety_audit_rejects_graphic_action(self):
        result = non_graphic_action_audit(["non-graphic crash", "blood close-up"])
        self.assertFalse(result["approved"])
