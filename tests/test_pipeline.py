"""Deterministic tests for the fundamental tools.

The tests these replace asserted that the string "gradient descent" routed to a
hand-written plan, which only confirmed the hardcoding was present. These
exercise the tools that made that hardcoding unnecessary, and need no API key.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from proofmotion.runtime.registry import ToolError, ToolRegistry
from proofmotion.tools import REGISTRY, toolset
from proofmotion.tools.layout import layout_check, layout_frame
from proofmotion.tools.manim_api import manim_signature, manim_validate_code
from proofmotion.tools.numeric import numeric_iterate, numeric_sample
from proofmotion.tools.symbolic import symbolic_differentiate, symbolic_verify_equality


class RegistryTests(unittest.TestCase):
    def test_schema_is_derived_from_the_signature(self):
        schema = next(s for s in REGISTRY.schemas() if s["function"]["name"] == "numeric_sample")["function"]
        properties = schema["parameters"]["properties"]
        self.assertEqual(properties["start"]["type"], "number")
        self.assertEqual(properties["count"]["type"], "integer")
        self.assertIn("expression", schema["parameters"]["required"])
        # Optional parameters must not be marked required, or every call fails.
        self.assertNotIn("count", schema["parameters"]["required"])

    def test_docstring_argument_help_reaches_the_model(self):
        schema = next(s for s in REGISTRY.schemas() if s["function"]["name"] == "symbolic_differentiate")["function"]
        self.assertTrue(schema["parameters"]["properties"]["variable"]["description"])

    def test_bad_arguments_raise_rather_than_defaulting(self):
        with self.assertRaises(ToolError):
            REGISTRY.dispatch("numeric_evaluate", {"wrong": 1})
        with self.assertRaises(ToolError):
            REGISTRY.dispatch("no_such_tool", {})

    def test_subset_rejects_unknown_names(self):
        self.assertIsInstance(toolset("manim"), ToolRegistry)
        with self.assertRaises(KeyError):
            toolset("nonexistent")


class ManimApiTests(unittest.TestCase):
    """The API is queried, not remembered — these pin that behaviour."""

    def test_catches_the_hallucinated_keyword_that_broke_a_render(self):
        code = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            "        axes = Axes()\n"
            "        g = axes.plot(lambda x: x**2)\n"
            "        axes.get_secant_slope_group(x=1.0, graph=g, dx=0.001, secant_line_width=4)\n"
        )
        report = manim_validate_code(code)
        self.assertFalse(report["valid"])
        problem = report["problems"][0]
        self.assertIn("secant_line_width", problem["problem"])
        self.assertIn("secant_line_length", problem["did_you_mean"])

    def test_does_not_flag_manims_own_example_scenes(self):
        example = Path("vendor/manim/example_scenes/basic.py")
        if not example.exists():
            self.skipTest("vendored manim not present")
        report = manim_validate_code(example.read_text(encoding="utf-8"))
        self.assertTrue(report["valid"], f"false positives: {report['problems']}")

    def test_signature_comes_from_the_installed_library(self):
        signature = manim_signature("Axes.get_secant_slope_group")
        names = {p["name"] for p in signature["parameters"]}
        self.assertIn("secant_line_length", names)
        self.assertNotIn("secant_line_width", names)

    def test_unknown_names_suggest_alternatives(self):
        with self.assertRaises(ToolError):
            manim_signature("Axees")


class SymbolicTests(unittest.TestCase):
    def test_derivative_is_computed_not_recalled(self):
        result = symbolic_differentiate("(x-2)**2 + 1")
        self.assertTrue(symbolic_verify_equality(result["result"], "2*x - 4")["equal"])

    def test_false_claims_are_refuted_with_a_counterexample(self):
        result = symbolic_verify_equality("(x+1)**2", "x**2 + 1")
        self.assertFalse(result["equal"])
        self.assertIsNotNone(result["counterexample"])

    def test_true_identities_are_confirmed(self):
        self.assertTrue(symbolic_verify_equality("(x+1)**2", "x**2 + 2*x + 1")["equal"])


class NumericTests(unittest.TestCase):
    def test_iteration_is_general_not_a_gradient_descent_special_case(self):
        # The same primitive that replaced gradient_descent_sequence.
        descent = numeric_iterate("x - 0.2*2*(x-2)", start=-2.0, steps=20)
        self.assertFalse(descent["diverged"])
        self.assertLess(abs(descent["trajectory"][-1] - 2), 0.01)

    def test_divergence_is_reported_not_hidden(self):
        result = numeric_iterate("x - 1.5*2*(x-2)", start=-2.0, steps=200)
        self.assertTrue(result["diverged"])

    def test_sampling_reports_the_range_axes_should_use(self):
        sample = numeric_sample("x**2", start=-3, stop=3, count=25)
        self.assertAlmostEqual(sample["y_max"], 9.0, places=6)
        self.assertAlmostEqual(sample["y_min"], 0.0, places=6)


class LayoutTests(unittest.TestCase):
    def test_overlapping_boxes_are_detected(self):
        result = layout_check(
            [
                {"name": "title", "x": 0, "y": 0, "width": 4, "height": 1},
                {"name": "equation", "x": 1, "y": 0.2, "width": 4, "height": 1},
            ]
        )
        self.assertFalse(result["ok"])
        self.assertEqual(result["overlaps"][0]["between"], ["title", "equation"])

    def test_objects_outside_the_frame_are_detected(self):
        frame = layout_frame()
        result = layout_check([{"name": "wide", "x": frame["right"], "y": 0, "width": 4, "height": 1}])
        self.assertFalse(result["ok"])
        self.assertIn("right", result["out_of_frame"][0]["sides"])

    def test_a_clear_layout_passes(self):
        self.assertTrue(
            layout_check(
                [
                    {"name": "title", "x": 0, "y": 3, "width": 4, "height": 0.8},
                    {"name": "graph", "x": 0, "y": 0, "width": 8, "height": 4},
                ]
            )["ok"]
        )


if __name__ == "__main__":
    unittest.main()
