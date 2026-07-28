"""Deterministic tests for the fundamental tools.

The tests these replace asserted that the string "gradient descent" routed to a
hand-written plan, which only confirmed the hardcoding was present. These
exercise the tools that made that hardcoding unnecessary, and need no API key.
"""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from proofmotion.pipeline import _is_competitive_exam_prompt, _is_creator_study_prompt
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

    def test_competitive_exam_prompts_are_detected_without_guessing(self):
        self.assertTrue(_is_competitive_exam_prompt("Solve this JEE Advanced mechanics question."))
        self.assertFalse(_is_competitive_exam_prompt("Explain a derivative visually."))

    def test_creator_study_prompts_enable_the_creator_layer(self):
        self.assertTrue(_is_creator_study_prompt("I am a content creator making a study animation."))
        self.assertTrue(_is_creator_study_prompt("Explain it in a 3Blue1Brown-like educational way."))
        self.assertFalse(_is_creator_study_prompt("Solve this algebra question."))


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

    def test_catches_axis_config_label_before_manim_forwards_it(self):
        code = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            "        axes = Axes(y_axis_config={\"label\": \"K_max\"})\n"
            "        self.add(axes)\n"
        )
        report = manim_validate_code(code)
        self.assertFalse(report["valid"])
        self.assertIn("axis configuration does not accept", report["problems"][0]["problem"])

    def test_catches_math_syntax_inside_text_mode_tex(self):
        code = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            "        subtitle = Tex(\"so that x^4 - a x^2 + 9 = 0 has roots\")\n"
            "        self.add(subtitle)\n"
        )
        report = manim_validate_code(code)
        self.assertFalse(report["valid"])
        self.assertIn("outside math mode", report["problems"][0]["problem"])

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

    def test_catches_a_colour_manim_does_not_have(self):
        """MAGENTA is not a Manim colour; it reached render and raised NameError."""
        code = "from manim import *\nclass GeneratedScene(Scene):\n    def construct(self):\n        self.add(Dot(color=MAGENTA))\n"
        report = manim_validate_code(code)
        self.assertFalse(report["valid"])
        self.assertEqual(report["problems"][0]["call"], "MAGENTA")
        self.assertIn("PURE_MAGENTA", report["problems"][0]["did_you_mean"])

    def test_catches_module_access_that_star_import_does_not_bind(self):
        """`from manim import *` imports the contents, not the name `manim`."""
        code = "from manim import *\nclass GeneratedScene(Scene):\n    def construct(self):\n        self.add(manim.Dot())\n"
        self.assertFalse(manim_validate_code(code)["valid"])
        with_import = "import manim\n" + code
        self.assertTrue(manim_validate_code(with_import)["valid"])

    def test_module_functions_are_not_mistaken_for_manim_methods(self):
        """np comes through Manim's star-export; np.zeros() is not a Manim method."""
        code = (
            "from manim import *\nclass GeneratedScene(Scene):\n"
            "    def construct(self):\n        a = np.zeros(4)\n        self.add(Dot())\n"
        )
        self.assertTrue(manim_validate_code(code)["valid"], manim_validate_code(code)["problems"])

    def test_rejects_component_beat_names_passed_to_animations(self):
        """Component beats are names; only the matching parts are Mobjects."""
        code = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            "        built = object()\n"
            "        self.play(*[FadeIn(part) for beat in built.beats for part in beat])\n"
        )
        report = manim_validate_code(code)
        self.assertFalse(report["valid"])
        self.assertIn("string part names", report["problems"][0]["problem"])

    def test_every_generated_scene_that_rendered_is_still_clean(self):
        """The validator must not flag code known to work."""
        def produced_a_video(project: Path) -> bool:
            # partial_movie_files exist even for failed renders, so a plain
            # *.mp4 glob counts scenes that never finished as successes.
            return any(
                "partial_movie_files" not in v.parts for v in (project / "preview").rglob("*.mp4")
            )

        rendered = [
            p
            for p in Path("generated_projects").glob("*/generated_scene.py")
            if p.stat().st_size and (p.parent / "preview").exists() and produced_a_video(p.parent)
        ]
        if not rendered:
            self.skipTest("no rendered projects available")
        for scene in rendered:
            report = manim_validate_code(scene.read_text(encoding="utf-8"))
            self.assertTrue(report["valid"], f"false positive in {scene}: {report['problems']}")


class ProviderTests(unittest.TestCase):
    """Provider differences that silently break requests if hardcoded."""

    def test_openai_uses_max_completion_tokens_and_others_do_not(self):
        from llm.providers import DeepSeekClient, OpenAIClient, OpenRouterClient

        # Verified against the live APIs: gpt-5.2 rejects max_tokens with a 400,
        # while DeepSeek and OpenRouter require exactly that name.
        self.assertEqual(OpenAIClient.token_param, "max_completion_tokens")
        self.assertEqual(DeepSeekClient.token_param, "max_tokens")
        self.assertEqual(OpenRouterClient.token_param, "max_tokens")

    def test_disabling_deepseek_thinking_is_sent_rather_than_omitted(self):
        """Both v4 models reason when the key is absent, so silence meant on.

        DEEPSEEK_THINKING=0 only stopped the code adding "enabled" — it never
        said "disabled" — so every run this setting claimed to have turned off
        was still reasoning. Measured on "what is 17*23": 61 completion tokens
        and a 154-character trace with the key omitted, 1 token with it
        explicitly disabled.
        """
        from llm.providers import DeepSeekClient

        self.assertEqual(
            DeepSeekClient(model="deepseek-v4-pro", thinking=False).extra_body,
            {"thinking": {"type": "disabled"}},
        )
        enabled = DeepSeekClient(model="deepseek-v4-pro", thinking=True, reasoning_effort="high").extra_body
        self.assertEqual(enabled["thinking"], {"type": "enabled"})
        self.assertEqual(enabled["reasoning_effort"], "high")

    @patch("llm.providers.time.sleep")
    def test_connection_error_retries_before_failing(self, sleep):
        from llm.providers import DeepSeekClient

        client = DeepSeekClient(model="deepseek-v4-flash")
        client._create = Mock(side_effect=[RuntimeError("Connection error"), Mock(choices=[Mock(message="ok")], usage=None)])
        result = client.chat([{"role": "user", "content": "test"}])
        self.assertEqual(result, "ok")
        self.assertEqual(client._create.call_count, 2)
        sleep.assert_called_once_with(1.0)

    def test_unsupported_parameters_are_read_from_the_api_error(self):
        from llm.providers import _unsupported_parameter

        # Both phrasings occur: gpt-5.6 rejects max_tokens as a "parameter" and
        # temperature as a "value".
        self.assertEqual(_unsupported_parameter("Unsupported parameter: 'max_tokens' is not supported"), "max_tokens")
        self.assertEqual(_unsupported_parameter("Unsupported value: 'temperature' does not support 0.2"), "temperature")
        self.assertIsNone(_unsupported_parameter("some unrelated failure"))

    def test_deepseek_dsml_tool_calls_are_normalized(self):
        from llm.providers import _decode_dsml_tool_calls

        response = (
            'I will calculate it.\n<｜｜DSML｜｜tool_calls>\n'
            '<｜｜DSML｜｜invoke name="symbolic_solve">\n'
            '<｜｜DSML｜｜parameter name="equation" string="true">x**2-4=0</｜｜DSML｜｜parameter>\n'
            '<｜｜DSML｜｜parameter name="variable" string="true">x</｜｜DSML｜｜parameter>\n'
            '</｜｜DSML｜｜invoke>\n</｜｜DSML｜｜tool_calls>'
        )
        calls = _decode_dsml_tool_calls(response)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].function.name, "symbolic_solve")
        self.assertEqual(calls[0].function.arguments, '{"equation": "x**2-4=0", "variable": "x"}')

    def test_forced_final_recovers_one_normalized_dsml_tool_call(self):
        from llm.providers import _Message, _ToolCall, _ToolFunction
        from proofmotion.runtime.loop import run_agent
        from proofmotion.runtime.registry import ToolRegistry

        registry = ToolRegistry()

        @registry.register
        def echo(value: str) -> dict[str, str]:
            """Return the supplied value."""
            return {"value": value}

        class Client:
            def __init__(self):
                self.messages = []
                self.responses = [
                    _Message("", [_ToolCall("normal", _ToolFunction("echo", '{"value":"first"}'))]),
                    _Message("", [_ToolCall("dsml-1", _ToolFunction("echo", '{"value":"second"}'))]),
                    _Message("{\"done\": true}"),
                ]

            def chat(self, messages, **kwargs):
                self.messages.append(messages)
                return self.responses.pop(0)

        result = run_agent(Client(), "system", "user", registry, max_iterations=1)
        self.assertEqual(result.content, '{"done": true}')
        self.assertEqual([call["name"] for call in result.tool_calls], ["echo", "echo"])

    def test_responses_tool_schema_is_flattened(self):
        from llm.providers import OpenAIResponsesClient

        # Chat nests the schema under "function"; Responses expects it flat.
        chat_style = [{"type": "function", "function": {"name": "f", "description": "d", "parameters": {"a": 1}}}]
        flat = OpenAIResponsesClient._to_responses_tools(chat_style)
        self.assertEqual(flat[0]["name"], "f")
        self.assertNotIn("function", flat[0])

    def test_responses_input_splits_system_and_tool_results(self):
        from llm.providers import OpenAIResponsesClient

        instructions, items = OpenAIResponsesClient._to_responses_input(
            [
                {"role": "system", "content": "be precise"},
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "", "tool_calls": [
                    {"id": "c1", "function": {"name": "f", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": "c1", "content": "result"},
            ]
        )
        self.assertEqual(instructions, "be precise")
        kinds = [i.get("type") or i.get("role") for i in items]
        self.assertEqual(kinds, ["user", "function_call", "function_call_output"])

    def test_every_provider_is_reachable_by_name(self):
        from llm.providers import PROVIDERS, LLMError, get_client

        self.assertIn("openai", PROVIDERS)
        with self.assertRaises(LLMError):
            get_client("nonexistent-provider")


class SceneInspectionTests(unittest.TestCase):
    """Measuring the written scene, not the planned one — where overlaps came from."""

    OVERLAPPING = (
        "from manim import *\n"
        "class GeneratedScene(Scene):\n"
        "    def construct(self):\n"
        "        a = Text('First Section Title').move_to(ORIGIN)\n"
        "        self.play(Write(a))\n"
        "        b = Text('Second Section Title').move_to(ORIGIN)\n"
        "        self.play(Write(b))\n"
    )
    CLEAN = (
        "from manim import *\n"
        "class GeneratedScene(Scene):\n"
        "    def construct(self):\n"
        "        a = Text('First Section Title').move_to(UP * 2)\n"
        "        self.play(Write(a))\n"
        "        self.play(FadeOut(a))\n"
        "        b = Text('Second Section Title').move_to(UP * 2)\n"
        "        self.play(Write(b))\n"
    )

    def test_text_drawn_over_text_is_detected(self):
        from proofmotion.tools.inspect_scene import inspect_scene

        report = inspect_scene(self.OVERLAPPING)
        self.assertFalse(report["ok"])
        self.assertTrue(report["text_overlaps"], "an overlap should have been measured")

    def test_a_scene_that_clears_the_stage_passes(self):
        from proofmotion.tools.inspect_scene import inspect_scene

        report = inspect_scene(self.CLEAN)
        self.assertTrue(report["ok"], report)

    def test_unreadably_small_text_is_flagged(self):
        from proofmotion.tools.inspect_scene import inspect_scene

        tiny = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            "        self.play(Write(Text('barely visible', font_size=6)))\n"
        )
        self.assertTrue(inspect_scene(tiny)["unreadable_text"])


class PacingTests(unittest.TestCase):
    def test_planner_never_caps_a_requested_derivation_by_duration(self):
        from proofmotion.agents.planner import SYSTEM

        self.assertNotIn("at most", SYSTEM)
        self.assertIn("Do not compress a derivation", SYSTEM)
        self.assertIn("final_answer_latex", SYSTEM)

    def test_numerical_question_is_treated_as_a_worked_problem(self):
        from proofmotion.pipeline import _is_worked_problem_prompt

        self.assertTrue(_is_worked_problem_prompt("A 2 kg mass moves under a force. Find its acceleration."))
        self.assertTrue(_is_worked_problem_prompt("Derive the time period of small oscillations."))
        self.assertFalse(_is_worked_problem_prompt("Visualize a sine wave."))

    def test_standard_hyperbola_prompt_uses_a_component_plan(self):
        from proofmotion.pipeline import _standard_hyperbola_plan

        plan = _standard_hyperbola_plan(
            "For the hyperbola x^2/a^2-y^2/b^2=1, one focus is (-3, 0), and "
            "the latus rectum subtends a right angle at the other focus. Find alpha + beta."
        )
        self.assertIsNotNone(plan)
        assert plan is not None
        self.assertTrue(all(scene.component == "conic_coordinate_diagram" for scene in plan.assignments))
        self.assertEqual(plan.assignments[-1].caption, r"\alpha+\beta=1944")


class RepairExtractionTests(unittest.TestCase):
    def test_code_is_recovered_from_a_reply_containing_prose(self):
        """A repair that explained itself first was returned verbatim and failed to parse."""
        from proofmotion.agents.coder import _strip_fences

        reply = (
            "Here is the fix → I replaced MAGENTA with PURPLE.\n\n"
            "```python\nfrom manim import *\n"
            "class GeneratedScene(Scene):\n    def construct(self):\n        self.add(Dot(color=PURPLE))\n```\n"
            "That should render now."
        )
        code = _strip_fences(reply)
        self.assertTrue(code.startswith("from manim"))
        self.assertIn("GeneratedScene", code)
        self.assertNotIn("→", code)


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
