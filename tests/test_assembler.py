"""The assembler emits scenes that render, without a model in the loop.

Composition used to depend on the coder taking a suggestion, and the numbers
said it mostly did not — 29% over the whole history, none of the last ten runs.
These tests hold the deterministic path to the standard the prompt could not
enforce: every emitted scene parses, passes API validation, and clears the stage
between sections.

No API key required.
"""

from __future__ import annotations

import ast
import logging
import unittest

logging.getLogger("manim").setLevel(logging.ERROR)

from proofmotion.components import COMPONENTS
from proofmotion.compose import (
    SceneAssignment,
    ScenePlan,
    assemble,
    check,
    coverage,
    estimated_seconds,
    pictorial_coverage,
    plan_from_storyboard,
)
from proofmotion.runtime.registry import ToolError
from proofmotion.tools.manim_api import manim_validate_code

PLOT = dict(expr="(x-2)**2+1", x_min=-1, x_max=5)


def plan(*assignments: SceneAssignment) -> ScenePlan:
    return ScenePlan(assignments=list(assignments))


class TestValidation(unittest.TestCase):
    def test_unknown_component_is_named_with_the_alternatives(self):
        problems = check(plan(SceneAssignment(component="not_a_component")))
        self.assertEqual(len(problems), 1)
        self.assertIn("not_a_component", problems[0])
        self.assertIn("function_plot", problems[0])

    def test_wrong_parameters_are_caught_before_rendering(self):
        """A bad parameter must come back as a sentence, not a traceback mid-render."""
        problems = check(plan(SceneAssignment(component="function_plot", parameters={"expr": "x**2", "x_min": "left"})))
        self.assertEqual(len(problems), 1)
        self.assertIn("function_plot", problems[0])

    def test_an_empty_scene_blocks_assembly(self):
        """No component and nothing to show is a blank frame, not a scene."""
        broken = plan(SceneAssignment(component=None))
        self.assertEqual(coverage(broken), 0.0)
        with self.assertRaises(ToolError):
            assemble(broken)

    def test_a_text_scene_does_not_send_the_whole_plan_to_the_coder(self):
        """One algebra scene among four used to cost the run its fast path."""
        mixed = plan(
            SceneAssignment(title="The curve", component="function_plot", parameters=PLOT),
            SceneAssignment(title="Differentiate", component=None, caption="f'(x)=2x-4"),
        )
        self.assertEqual(coverage(mixed), 0.5)
        self.assertEqual(check(mixed), [])
        code = assemble(mixed)
        ast.parse(code)
        self.assertEqual(manim_validate_code(code)["valid"], True)
        # The equation is the scene, so it goes on the stage, not the caption strip.
        self.assertIn("place(caption, regions['stage'])", code)

    def test_coverage_is_the_fraction_a_component_can_express(self):
        mixed = plan(
            SceneAssignment(component="function_plot", parameters=PLOT),
            SceneAssignment(component=None),
        )
        self.assertEqual(coverage(mixed), 0.5)


class TestAssemblyGate(unittest.TestCase):
    """When a plan is mostly words, the coder must get it instead.

    A question asking for full diagrams came back as four equation slides on a
    black background. Both agents had searched and correctly found that nothing
    covered the setup — but assembly accepted a plan with zero components and
    reported success, so the coder, which draws what no component covers, was
    never asked.
    """

    def test_the_threshold_rejects_a_plan_with_no_components(self):
        from proofmotion.pipeline import MIN_ASSEMBLY_COVERAGE

        words_only = plan(
            SceneAssignment(title="Zero angular momentum", caption="L=0"),
            SceneAssignment(title="Balance", caption="I_1=I_2"),
        )
        self.assertEqual(coverage(words_only), 0.0)
        self.assertLess(pictorial_coverage(words_only), MIN_ASSEMBLY_COVERAGE)

    def test_equation_chain_does_not_count_as_a_picture(self):
        """The gate's first version passed this run at 0.75 coverage.

        Every scene used equation_chain, which is a component and draws no
        picture, so a question asking for full diagrams came back as four
        screens of algebra and the coder was never asked.
        """
        algebra = plan(
            SceneAssignment(title="Conservation", component="equation_chain",
                            parameters={"steps": ["L=0", "I_1 w_1 = I_2 w_2"]}),
            SceneAssignment(title="Substitute", component="equation_chain",
                            parameters={"steps": ["I=MR^2/2", "n=13"]}),
        )
        self.assertEqual(coverage(algebra), 1.0)        # every scene has a component
        self.assertEqual(pictorial_coverage(algebra), 0.0)  # and none of them draws

    def test_a_drawing_component_counts_as_a_picture(self):
        drawn = plan(SceneAssignment(component="function_plot", parameters=PLOT))
        self.assertEqual(pictorial_coverage(drawn), 1.0)

    def test_the_threshold_rejects_a_plan_that_is_mostly_words(self):
        from proofmotion.pipeline import MIN_ASSEMBLY_COVERAGE

        mostly_words = plan(
            SceneAssignment(component="function_plot", parameters=PLOT),
            SceneAssignment(title="a", caption="x=1"),
            SceneAssignment(title="b", caption="y=2"),
            SceneAssignment(title="c", caption="z=3"),
        )
        self.assertLess(pictorial_coverage(mostly_words), MIN_ASSEMBLY_COVERAGE)

    def test_the_threshold_accepts_a_plan_components_carry(self):
        from proofmotion.pipeline import MIN_ASSEMBLY_COVERAGE

        carried = plan(
            SceneAssignment(component="function_plot", parameters=PLOT),
            SceneAssignment(component="tangent_secant", parameters={**PLOT, "at": 3.0}),
            SceneAssignment(title="Result", caption="f'(3)=2"),
        )
        self.assertGreaterEqual(pictorial_coverage(carried), MIN_ASSEMBLY_COVERAGE)


class TestEmission(unittest.TestCase):
    def scene(self) -> str:
        return assemble(
            plan(
                SceneAssignment(title="The curve", component="function_plot", parameters=PLOT, caption="f(x)=x^2", seconds=8),
                SceneAssignment(title="Tangent", component="tangent_secant", parameters={**PLOT, "at": 3.0}, seconds=10),
            )
        )

    def test_emitted_scene_parses_and_validates(self):
        code = self.scene()
        ast.parse(code)
        self.assertIn("class GeneratedScene(Scene):", code)
        self.assertEqual(manim_validate_code(code), {"valid": True, "problems": []})

    def test_the_words_are_cleared_between_scenes(self):
        """The defect this path exists to remove: two sections drawn over each other."""
        code = self.scene()
        self.assertEqual(code.count("FadeOut(m) for m in chrome"), 2)  # once per scene
        self.assertIn("FadeOut(m) for m in leaving", code)  # and everything at the end

    def test_a_changed_picture_is_replaced(self):
        code = self.scene()
        self.assertEqual(code.count("self.play(FadeOut(stage), run_time=0.4)"), 2)

    def test_an_unchanged_picture_stays_on_screen(self):
        """Rebuilding an identical figure made the viewer watch it flicker.

        Four scenes about one tangent line produced four teardown/rebuild
        cycles of the same parabola, each individually correct.
        """
        repeated = plan(
            SceneAssignment(title="The tangent", component="tangent_secant", parameters={**PLOT, "at": 3.0}, caption="f'(3)=2"),
            SceneAssignment(title="Rise over run", component="tangent_secant", parameters={**PLOT, "at": 3.0}, caption="m=2"),
            SceneAssignment(title="Derivative", component="tangent_secant", parameters={**PLOT, "at": 3.0}),
        )
        code = assemble(repeated)
        ast.parse(code)
        self.assertEqual(manim_validate_code(code)["valid"], True)
        self.assertEqual(code.count("built = build("), 1)  # built once, not three times
        self.assertEqual(code.count("unchanged from the previous scene"), 2)
        # The words still change on every scene.
        self.assertEqual(code.count("FadeOut(m) for m in chrome"), 3)
        self.assertIn("Rise over run", code)

    def test_a_different_parameter_rebuilds_the_picture(self):
        """Same component, different `at` — that is a new picture, not a repeat."""
        moving = plan(
            SceneAssignment(component="tangent_secant", parameters={**PLOT, "at": 2.0}),
            SceneAssignment(component="tangent_secant", parameters={**PLOT, "at": 3.0}),
        )
        code = assemble(moving)
        self.assertEqual(code.count("built = build("), 2)
        self.assertNotIn("unchanged from the previous scene", code)

    def test_an_equation_scene_clears_the_picture(self):
        mixed = plan(
            SceneAssignment(component="function_plot", parameters=PLOT),
            SceneAssignment(title="Differentiate", component=None, caption="f'(x)=2x-4"),
        )
        code = assemble(mixed)
        self.assertIn("stage = None", code)
        self.assertEqual(manim_validate_code(code)["valid"], True)

    def test_titles_and_captions_are_placed_in_regions_not_by_hand(self):
        code = self.scene()
        self.assertIn("place(title, regions['title'])", code)
        self.assertIn("place(caption, regions['caption'])", code)
        self.assertNotIn(".to_edge(", code)
        self.assertNotIn(".next_to(", code)

    def test_text_is_never_emitted_below_the_readable_floor(self):
        code = self.scene()
        sizes = [int(line.split("font_size=")[1].split(")")[0]) for line in code.splitlines() if "font_size=" in line]
        self.assertTrue(sizes)
        self.assertGreaterEqual(min(sizes), 28)

    def test_a_scene_without_a_title_or_caption_still_emits(self):
        code = assemble(plan(SceneAssignment(component="function_plot", parameters=PLOT)))
        ast.parse(code)
        self.assertNotIn("Text(", code)
        self.assertNotIn("MathTex(", code)

    def test_estimated_length_tracks_the_requested_seconds(self):
        self.assertEqual(
            estimated_seconds(plan(
                SceneAssignment(component="function_plot", parameters=PLOT, seconds=8),
                SceneAssignment(component="function_plot", parameters=PLOT, seconds=12),
            )),
            20.0,
        )

    def test_strings_with_quotes_and_backslashes_survive_emission(self):
        """Captions are LaTeX. Emitting them naively is how \\frac becomes a bug."""
        code = assemble(plan(
            SceneAssignment(
                title="It's \"quoted\"",
                component="function_plot",
                parameters=PLOT,
                caption=r"\frac{d}{dx}\left(x^2\right)",
            )
        ))
        tree = ast.parse(code)
        literals = {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        self.assertIn(r"\frac{d}{dx}\left(x^2\right)", literals)
        self.assertIn('It\'s "quoted"', literals)


class TestDerivation(unittest.TestCase):
    """Reading the plan out of the storyboard, when it can be read at all."""

    def storyboard(self, *scenes) -> dict:
        return {"teaching_strategy": "t", "scenes": list(scenes)}

    def scene(self, objects, equations=(), seconds=7.0) -> dict:
        return {
            "scene_id": "s",
            "purpose": "p",
            "duration_seconds": seconds,
            "visual_objects": list(objects),
            "equations": list(equations),
        }

    def test_a_clean_storyboard_needs_no_model_call(self):
        plan = plan_from_storyboard(
            self.storyboard(
                self.scene([{"name": "function_plot", "parameters": PLOT}], ["f(x)=x^2"]),
                self.scene([{"name": "tangent_secant", "parameters": {**PLOT, "at": 3.0}}]),
            )
        )
        self.assertIsNotNone(plan)
        self.assertEqual([a.component for a in plan.assignments], ["function_plot", "tangent_secant"])
        self.assertEqual(manim_validate_code(assemble(plan))["valid"], True)

    def test_loose_shapes_beside_a_component_are_not_derivable(self):
        """The regression that would have shipped four identical parabolas.

        A director describing a tangent writes function_plot first and the
        tangent line as a loose shape. Taking the first match renders the plot
        alone: valid, and missing the entire point of the scene.
        """
        plan = plan_from_storyboard(
            self.storyboard(
                self.scene([
                    {"name": "function_plot", "parameters": PLOT},
                    {"name": "tangent", "parameters": {"at": 3.0}},
                ])
            )
        )
        self.assertIsNone(plan)

    def test_two_components_in_one_scene_are_not_derivable(self):
        plan = plan_from_storyboard(
            self.storyboard(
                self.scene([
                    {"name": "function_plot", "parameters": PLOT},
                    {"name": "tangent_secant", "parameters": {**PLOT, "at": 3.0}},
                ])
            )
        )
        self.assertIsNone(plan)

    def test_invalid_parameters_are_not_derivable(self):
        plan = plan_from_storyboard(
            self.storyboard(self.scene([{"name": "function_plot", "parameters": {"expr": "x**2", "x_min": "left"}}]))
        )
        self.assertIsNone(plan)

    def test_a_storyboard_of_pure_equations_goes_to_the_selector(self):
        """All-text is a storyboard the director never grounded; look again."""
        plan = plan_from_storyboard(self.storyboard(self.scene([], ["f(x)=x^2"]), self.scene([], ["f'(x)=2x"])))
        self.assertIsNone(plan)

    def test_a_scene_with_nothing_in_it_is_not_derivable(self):
        plan = plan_from_storyboard(
            self.storyboard(self.scene([{"name": "function_plot", "parameters": PLOT}]), self.scene([], []))
        )
        self.assertIsNone(plan)

    def test_the_directors_title_reaches_the_screen(self):
        """Derived scenes shipped untitled until the storyboard carried a heading."""
        scene = self.scene([{"name": "function_plot", "parameters": PLOT}])
        scene["title"] = "Slope of the tangent"
        scene["purpose"] = "A long sentence written for the pipeline, not for the screen."
        plan = plan_from_storyboard(self.storyboard(scene))
        self.assertEqual(plan.assignments[0].title, "Slope of the tangent")
        self.assertIn("Slope of the tangent", assemble(plan))
        self.assertNotIn("written for the pipeline", assemble(plan))

    def test_scene_durations_carry_through(self):
        plan = plan_from_storyboard(
            self.storyboard(self.scene([{"name": "function_plot", "parameters": PLOT}], seconds=12.0))
        )
        self.assertEqual(plan.assignments[0].seconds, 12.0)

    def test_an_empty_storyboard_is_not_derivable(self):
        self.assertIsNone(plan_from_storyboard({"scenes": []}))
        self.assertIsNone(plan_from_storyboard({}))


class TestEveryComponentAssembles(unittest.TestCase):
    """Any component the selector may choose must emit a scene that validates.

    A component that cannot be assembled is one the fast path silently never
    uses, which is exactly the failure mode this replaces.
    """

    def test_all_registered_components_emit_valid_scenes(self):
        covered = 0
        for name, spec in sorted(COMPONENTS.items()):
            fields = spec.params.model_fields
            if any(info.is_required() for info in fields.values()):
                # Required parameters have no safe stand-in here; test_components
                # exercises those at their extremes.
                continue
            with self.subTest(component=name):
                defaults = {field: info.default for field, info in fields.items()}
                code = assemble(plan(SceneAssignment(title=name, component=name, parameters=defaults)))
                ast.parse(code)
                self.assertEqual(manim_validate_code(code)["valid"], True, name)
                covered += 1
        # Guard against the loop silently covering nothing, which is how this
        # test would pass while testing no component at all.
        self.assertGreater(covered, 5, "too few components exercised")


if __name__ == "__main__":
    unittest.main()
