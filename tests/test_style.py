"""Style presets: one palette, honest digests, and a stable default.

The one rule that must hold across all of it: the default deck is
byte-identical to a deck rendered before styles existed — its digests do not
move — and any other preset moves every digest, because a restyle is a
re-render and pretending otherwise would serve stale clips.

No API key required.
"""

from __future__ import annotations

import dataclasses
import re
import unittest

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import Slide, digest_of

PLOT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


class TestPresets(unittest.TestCase):
    def test_every_preset_fills_every_role_with_a_color(self):
        from proofmotion.components.palette import Palette, PRESETS

        for preset in PRESETS.values():
            for slot in dataclasses.fields(Palette):
                value = getattr(preset, slot.name)
                with self.subTest(preset=preset.name, role=slot.name):
                    if slot.name in ("name", "font"):
                        self.assertIsInstance(value, str)
                    else:
                        self.assertRegex(value, HEX)

    def test_activate_mutates_the_one_palette_in_place(self):
        """Module-level `from palette import PALETTE` must see the change."""
        from proofmotion.components.palette import PALETTE, activate

        before = id(PALETTE)
        try:
            activate("paper")
            self.assertEqual(id(PALETTE), before)
            self.assertEqual(PALETTE.background, "#faf7f0")
        finally:
            activate("dark")
        self.assertEqual(PALETTE.accent, "#4aa3df")

    def test_an_unknown_style_is_refused_with_the_choices(self):
        from proofmotion.components.palette import activate

        with self.assertRaises(ToolError) as caught:
            activate("neon")
        self.assertIn("paper", str(caught.exception))


class TestEmission(unittest.TestCase):
    def plan(self):
        from proofmotion.compose.assembler import SceneAssignment, ScenePlan

        return ScenePlan(assignments=[
            SceneAssignment(title="One", component="function_plot", parameters=PLOT)
        ])

    def test_the_scene_source_activates_its_style(self):
        from proofmotion.compose.assembler import assemble

        self.assertIn("activate('chalkboard')", assemble(self.plan(), style="chalkboard"))
        self.assertIn("activate('dark')", assemble(self.plan()))

    def test_a_hand_written_scene_gets_the_prologue(self):
        from proofmotion.studio.render import _styled

        styled = _styled("from manim import *\n\nclass GeneratedScene(Scene):\n    pass\n", "paper")
        first_two = styled.splitlines()[:2]
        self.assertEqual(first_two, [
            "from proofmotion.components.palette import activate",
            "activate('paper')",
        ])


class TestDigests(unittest.TestCase):
    def test_the_default_look_leaves_digests_where_they_were(self):
        """Every project rendered before styles existed keeps its clips."""
        plain = Slide(id="s1", component="function_plot", parameters=PLOT)
        self.assertEqual(
            digest_of([plain]),
            digest_of([plain], style="dark", quality="l"),
        )

    def test_any_other_look_moves_every_digest(self):
        plain = Slide(id="s1", component="function_plot", parameters=PLOT)
        base = digest_of([plain])
        self.assertNotEqual(base, digest_of([plain], style="paper"))
        self.assertNotEqual(base, digest_of([plain], quality="m"))


if __name__ == "__main__":
    unittest.main()
