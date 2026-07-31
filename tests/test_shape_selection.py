"""Shape-first selection: the retrieval, the guard, and the fallback routing.

The gap S8/S9 closes was never coverage — it was that a miss had nowhere to
go. These tests hold the three legs of the fix: the five shape components are
always retrievable with full schemas, their number is capped by design, and
the zero-coverage fallback routes a plan's structure to the shape it has.

No API key required.
"""

from __future__ import annotations

import unittest

from proofmotion.components import COMPONENTS
from proofmotion.tools.components_tool import component_search


class TestShapeRetrieval(unittest.TestCase):
    def test_every_search_returns_all_five_shapes_with_their_schemas(self):
        """A shape pushed below the schema cutoff is a miss with nowhere to fall."""
        for query in ("anything at all", "riemann sums", ""):
            with self.subTest(query=query):
                out = component_search(query)
                shapes = out["shapes"]
                self.assertEqual(len(shapes), 5)
                for entry in shapes:
                    self.assertIn("parameters", entry)
                    self.assertTrue(entry["parameters"], entry["name"])
                    self.assertTrue(entry["use_when"], entry["name"])

    def test_shapes_are_not_double_listed(self):
        out = component_search("process pipeline stages")
        ranked = {e["name"] for e in out["components"]} | {
            e["name"] for e in out["rest_of_catalogue"]
        }
        self.assertFalse(ranked & {e["name"] for e in out["shapes"]})

    def test_subject_retrieval_is_not_regressed(self):
        out = component_search("riemann area under curve")
        detailed = [e["name"] for e in out["components"]]
        self.assertIn("riemann_area", detailed)

    def test_the_note_opens_with_the_shape_question(self):
        self.assertTrue(component_search("x")["note"].startswith("Name the shape"))


class TestShapeGuard(unittest.TestCase):
    def test_exactly_five_components_carry_a_shape(self):
        """PLAN-STUDIO-II §5: the shapes must not become a catalogue to miss.

        A sixth shape component is a design decision, not an addition — this
        failing is the point at which that decision gets made consciously.
        """
        shaped = {name: spec.shape for name, spec in COMPONENTS.items() if spec.shape}
        self.assertEqual(len(shaped), 5, shaped)
        self.assertEqual(
            set(shaped.values()), {"sequence", "comparison", "tree", "stack", "grid"}
        )

    def test_subject_components_describe_no_shape(self):
        self.assertNotIn("shape", COMPONENTS["function_plot"].describe())
        self.assertEqual(COMPONENTS["flow_diagram"].describe()["shape"], "sequence")


class TestShapeFallback(unittest.TestCase):
    def plan_state(self, topic: str, concepts: list[str]) -> dict:
        return {
            "intent": {"topic": topic, "domain": "general"},
            "math_plan": {"concept_sequence": [{"concept": c} for c in concepts]},
        }

    def test_a_process_falls_to_a_flow_diagram(self):
        from proofmotion.compose.shapes import shape_fallback

        ops = shape_fallback(self.plan_state("How RSA works", ["keygen", "encrypt", "decrypt"]))
        self.assertEqual(len(ops), 1)
        self.assertEqual(ops[0].component, "flow_diagram")
        self.assertEqual(ops[0].parameters["stages"], ["keygen", "encrypt", "decrypt"])

    def test_a_long_sequence_keeps_both_ends(self):
        from proofmotion.compose.shapes import shape_fallback

        ops = shape_fallback(self.plan_state("A long proof", [f"step {i}" for i in range(1, 14)]))
        stages = ops[0].parameters["stages"]
        self.assertEqual(len(stages), 8)
        self.assertEqual(stages[0], "step 1")
        self.assertEqual(stages[-1], "step 13")

    def test_a_stack_question_falls_to_layers(self):
        from proofmotion.compose.shapes import shape_fallback

        ops = shape_fallback(self.plan_state(
            "The OSI protocol stack",
            ["physical", "data link", "network", "transport", "application"],
        ))
        self.assertEqual(ops[0].component, "layers")
        self.assertEqual(ops[0].parameters["layers"][0], "physical")

    def test_one_step_is_no_shape(self):
        from proofmotion.compose.shapes import shape_fallback

        self.assertEqual(shape_fallback(self.plan_state("tiny", ["only step"])), [])


class TestPromptDrift(unittest.TestCase):
    def test_all_three_selection_prompts_carry_the_shape_paragraph(self):
        """One constant, three prompts — this is the cheap guard against a
        fourth copy appearing or one of the three quietly losing it."""
        from proofmotion.agents.director import SYSTEM as director
        from proofmotion.agents.studio import SYSTEM as studio
        from proofmotion.compose.selector import SYSTEM as selector

        for name, text in (("selector", selector), ("director", director), ("studio", studio)):
            with self.subTest(prompt=name):
                self.assertIn("name the shape of the idea", text)


if __name__ == "__main__":
    unittest.main()
