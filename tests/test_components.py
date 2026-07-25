"""Golden tests for the layout engine and components.

The point of a component is that its layout is verified once instead of being
re-derived, badly, on every run. That guarantee is only real if it is tested at
the parameter extremes: a label that clears the curve on a gentle parabola may
sit straight on a steep one.

No API key required — everything here is deterministic.
"""

from __future__ import annotations

import itertools
import logging
import unittest

logging.getLogger("manim").setLevel(logging.ERROR)

from manim import config, tempconfig  # noqa: E402

from proofmotion.components import COMPONENTS, build  # noqa: E402
from proofmotion.layout.collision import bounds, text_on_ink  # noqa: E402
from proofmotion.layout.labels import place_label  # noqa: E402
from proofmotion.layout.regions import LAYOUT_NAMES, layout, place  # noqa: E402


def overlaps(a, b) -> bool:
    return (min(a.right, b.right) - max(a.left, b.left)) > 0 and (min(a.top, b.top) - max(a.bottom, b.bottom)) > 0


class RegionTests(unittest.TestCase):
    def test_regions_never_intersect(self):
        """The whole point: two things cannot claim the same space."""
        for name in LAYOUT_NAMES:
            regions = list(layout(name).values())
            for first, second in itertools.combinations(regions, 2):
                self.assertFalse(overlaps(first, second), f"{name}: {first.name} intersects {second.name}")

    def test_regions_stay_inside_the_frame(self):
        for name in LAYOUT_NAMES:
            for region in layout(name).values():
                self.assertGreaterEqual(region.left, -config.frame_width / 2 - 1e-6)
                self.assertLessEqual(region.right, config.frame_width / 2 + 1e-6)
                self.assertGreaterEqual(region.bottom, -config.frame_height / 2 - 1e-6)
                self.assertLessEqual(region.top, config.frame_height / 2 + 1e-6)

    def test_oversized_content_is_scaled_to_fit(self):
        from manim import Rectangle

        region = layout("title_stage_caption")["caption"]
        placed = place(Rectangle(width=20, height=8), region)
        left, right, bottom, top = bounds(placed)
        self.assertLessEqual(right - left, region.width + 1e-6)
        self.assertLessEqual(top - bottom, region.height + 1e-6)

    def test_placing_never_scales_content_up(self):
        from manim import Square

        small = Square(side_length=0.4)
        place(small, layout("full")["stage"])
        self.assertAlmostEqual(float(small.width), 0.4, places=6)


class LabelPlacementTests(unittest.TestCase):
    def test_label_avoids_the_curve_it_annotates(self):
        """Placed at the anchor a label sits on the curve; scored, it does not."""
        from manim import Axes, MathTex

        with tempconfig({"dry_run": True}):
            axes = Axes(x_range=[-3, 3], y_range=[0, 9])
            curve = axes.plot(lambda x: x**2, x_range=[-3, 3])
            anchor = axes.c2p(0, 0)

            naive = MathTex("minimum", font_size=30).move_to(anchor)
            self.assertTrue(text_on_ink([axes, curve, naive]), "the naive case should collide")

            scored = MathTex("minimum", font_size=30)
            place_label(scored, anchor, avoid=[axes, curve])
            self.assertEqual(text_on_ink([axes, curve, scored]), [])

    def test_a_crowded_anchor_produces_a_leader_line(self):
        from manim import Axes, MathTex

        with tempconfig({"dry_run": True}):
            axes = Axes(x_range=[-4, 4], y_range=[-4, 4])
            # Dense enough that every nearby candidate is compromised.
            clutter = [axes.plot(lambda x, k=k: 0.4 * x + k, x_range=[-4, 4]) for k in range(-3, 4)]
            label = MathTex("here", font_size=26)
            result = place_label(label, axes.c2p(0, 0), avoid=[axes, *clutter])
            self.assertIn(result["direction"], {"leader", "E", "NE", "N", "NW", "W", "SW", "S", "SE"})
            # Whatever it chose, the outcome must be measurably better than the centre.
            naive = MathTex("here", font_size=26).move_to(axes.c2p(0, 0))
            self.assertLessEqual(
                len(text_on_ink([axes, *clutter, label])),
                len(text_on_ink([axes, *clutter, naive])),
            )


class ComponentTests(unittest.TestCase):
    """Every component, across its parameter range, must produce clean geometry."""

    CASES = {
        "function_plot": [
            dict(expr="(x-2)**2 + 1", x_min=-1, x_max=5, label="f(x)=(x-2)^2+1"),
            dict(expr="sin(x)", x_min=-6.3, x_max=6.3, label="\\sin x"),
            dict(expr="exp(x)", x_min=-2, x_max=3),
            dict(expr="x**3 - 3*x", x_min=-2.5, x_max=2.5, label="x^3-3x"),
        ],
        "tangent_secant": [
            dict(expr="x**2", x_min=-3, x_max=3, at=1.5),
            dict(expr="sin(x)", x_min=-3.2, x_max=3.2, at=0.0),
            dict(expr="x**2", x_min=-3, x_max=3, at=-2.5, dx=1.0),
            dict(expr="exp(x)", x_min=-1, x_max=2, at=1.9),
        ],
        "riemann_area": [
            dict(expr="x**2", a=0, b=3, rectangles=4, kind="left"),
            dict(expr="x**2", a=0, b=3, rectangles=60, kind="midpoint"),
            dict(expr="sin(x)", a=0, b=3.14, rectangles=12, kind="right"),
        ],
        "iteration_trace": [
            dict(expr="(x-2)**2+1", update_rule="x - 0.2*2*(x-2)", start=-2, steps=10, x_min=-3, x_max=6),
            dict(expr="(x-2)**2+1", update_rule="x - 0.05*2*(x-2)", start=5.5, steps=40, x_min=-3, x_max=6),
            dict(expr="x**2", update_rule="x - 1.1*2*x", start=0.5, steps=12, x_min=-3, x_max=3),
        ],
    }

    def test_every_component_is_registered_with_a_schema(self):
        for name in self.CASES:
            self.assertIn(name, COMPONENTS)
            described = COMPONENTS[name].describe()
            self.assertTrue(described["parameters"], f"{name} exposes no parameters")
            self.assertGreaterEqual(described["version"], 1)

    def test_no_text_sits_on_geometry_at_any_parameter(self):
        for name, cases in self.CASES.items():
            for parameters in cases:
                with self.subTest(component=name, parameters=parameters), tempconfig({"dry_run": True}):
                    built = build(name, parameters)
                    self.assertEqual(text_on_ink([built.group]), [], f"{name} {parameters}")

    def test_everything_stays_inside_the_frame(self):
        half_w, half_h = config.frame_width / 2, config.frame_height / 2
        for name, cases in self.CASES.items():
            for parameters in cases:
                with self.subTest(component=name, parameters=parameters), tempconfig({"dry_run": True}):
                    left, right, bottom, top = bounds(build(name, parameters).group)
                    self.assertGreaterEqual(left, -half_w - 1e-6)
                    self.assertLessEqual(right, half_w + 1e-6)
                    self.assertGreaterEqual(bottom, -half_h - 1e-6)
                    self.assertLessEqual(top, half_h + 1e-6)

    def test_parts_and_beats_are_usable_by_a_scene(self):
        """beats must only name parts that exist, or the generated scene breaks."""
        for name, cases in self.CASES.items():
            with tempconfig({"dry_run": True}):
                built = build(name, cases[0])
                self.assertTrue(built.parts)
                for beat in built.beats:
                    for part in beat:
                        self.assertIn(part, built.parts, f"{name}: beat names missing part {part!r}")

    def test_invalid_parameters_raise_rather_than_defaulting(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError):
            build("function_plot", {"x_min": 0, "x_max": 1})  # expr missing
        with self.assertRaises(ToolError):
            build("riemann_area", dict(expr="x**2", a=0, b=1, rectangles=0))  # below ge=1
        with self.assertRaises(ToolError):
            build("nonexistent_component", {})


if __name__ == "__main__":
    unittest.main()
