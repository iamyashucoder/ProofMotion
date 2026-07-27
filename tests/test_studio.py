"""The document, the edit vocabulary, and the cache that makes editing cheap.

The claim this file has to hold is narrow and load-bearing: touching one slide
re-renders one slide. If a digest moves when it should not, or a slide id is
reused, the studio quietly re-renders the whole video and the reason for the
design is gone.

No API key required.
"""

from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

logging.getLogger("manim").setLevel(logging.ERROR)

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import Project, Slide, digest_of, group, units_of
from proofmotion.studio.operations import Operation, apply, apply_all, touched

PLOT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0}


def slide(sid: str, component: str | None = "function_plot", **kwargs) -> Slide:
    return Slide(id=sid, component=component, parameters=dict(kwargs.pop("parameters", PLOT)), **kwargs)


def project(*slides: Slide) -> Project:
    p = Project.create("test", "a question")
    p.slides = list(slides)
    return p


class TestDocument(unittest.TestCase):
    def test_a_project_round_trips_through_disk(self):
        p = project(slide("s1", title="One"), slide("s2", title="Two", locked=True))
        with tempfile.TemporaryDirectory() as tmp:
            p.save(tmp)
            back = Project.load(Path(tmp))
        self.assertEqual([s.id for s in back.slides], ["s1", "s2"])
        self.assertTrue(back.slides[1].locked)
        self.assertEqual(back.question, "a question")

    def test_an_unreadable_document_raises_rather_than_coercing(self):
        """A project whose components moved under it must say so."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "project.json").write_text('{"nope": true}', encoding="utf-8")
            with self.assertRaises(ToolError):
                Project.load(Path(tmp))

    def test_a_deleted_id_is_never_reissued(self):
        """A reused id collides with the cached clip of the slide that is gone.

        Counting slides would hand s2 back out after s2 was deleted, and the
        new slide would render as the old one.
        """
        p = project(slide("s1"), slide("s2"), slide("s3"))
        apply(p, Operation(kind="delete", slide_id="s2"))
        self.assertEqual(p.next_id(), "s4")
        self.assertNotIn(p.next_id(), {s.id for s in p.slides})


class TestRunGrouping(unittest.TestCase):
    """Slides sharing a figure render together, so the held figure survives."""

    def test_consecutive_slides_with_one_figure_form_a_run(self):
        runs = group([
            slide("s1", title="a"), slide("s2", title="b"), slide("s3", title="c"),
        ])
        self.assertEqual([[s.id for s in r] for r in runs], [["s1", "s2", "s3"]])

    def test_a_changed_parameter_starts_a_new_run(self):
        runs = group([
            slide("s1"),
            slide("s2", parameters={**PLOT, "x_max": 5.0}),
        ])
        self.assertEqual(len(runs), 2)

    def test_a_text_slide_never_joins_a_run(self):
        runs = group([slide("s1"), slide("s2", component=None, parameters={}, caption="x=1"), slide("s3")])
        self.assertEqual([[s.id for s in r] for r in runs], [["s1"], ["s2"], ["s3"]])


class TestDigest(unittest.TestCase):
    """The cache key. Everything that changes the pixels, and nothing else."""

    def test_the_same_content_hashes_the_same(self):
        self.assertEqual(digest_of([slide("s1", title="a")]), digest_of([slide("s9", title="a")]))

    def test_content_changes_move_the_digest(self):
        base = digest_of([slide("s1", title="a", caption="c", seconds=6.0)])
        for changed in (
            slide("s1", title="different", caption="c", seconds=6.0),
            slide("s1", title="a", caption="other", seconds=6.0),
            slide("s1", title="a", caption="c", seconds=9.0),
            slide("s1", title="a", caption="c", seconds=6.0, parameters={**PLOT, "x_max": 4.0}),
        ):
            with self.subTest(changed=changed.title):
                self.assertNotEqual(base, digest_of([changed]))

    def test_the_component_version_is_part_of_the_key(self):
        """Improving a component must invalidate clips built from the old one.

        Otherwise an edited project silently mixes two generations of the same
        figure — the edited slide new, the rest as they were months ago.
        """
        from proofmotion.components import COMPONENTS

        spec = COMPONENTS["function_plot"]
        before = digest_of([slide("s1")])
        original = spec.version
        try:
            spec.version = original + 1
            self.assertNotEqual(before, digest_of([slide("s1")]))
        finally:
            spec.version = original

    def test_locking_a_slide_does_not_move_the_digest(self):
        """Locking changes no pixels, so it must not cost a render."""
        plain, locked = slide("s1"), slide("s1", locked=True)
        self.assertEqual(digest_of([plain]), digest_of([locked]))

    def test_editing_one_slide_leaves_the_other_digests_alone(self):
        """The whole claim: one edit, one re-render."""
        p = project(slide("s1", title="a"), slide("s2", title="b", parameters={**PLOT, "x_max": 4.0}),
                    slide("s3", title="c", parameters={**PLOT, "x_max": 5.0}))
        before = [u.digest for u in units_of(p)]
        apply(p, Operation(kind="edit", slide_id="s2", title="changed"))
        after = [u.digest for u in units_of(p)]
        self.assertEqual(before[0], after[0])
        self.assertEqual(before[2], after[2])
        self.assertNotEqual(before[1], after[1])

    def test_reordering_re_renders_nothing(self):
        p = project(slide("s1", title="a"), slide("s2", title="b", parameters={**PLOT, "x_max": 4.0}))
        before = {u.digest for u in units_of(p)}
        apply(p, Operation(kind="reorder", slide_id="s1"))
        self.assertEqual([s.id for s in p.slides], ["s2", "s1"])
        self.assertEqual(before, {u.digest for u in units_of(p)})


class TestNotation(unittest.TestCase):
    """Unicode maths a model writes, turned into LaTeX that compiles.

    Three clips in a row failed on the approximately-equal sign alone, and the
    error named a file in vendored Manim rather than the caption the person had
    just asked for.
    """

    def test_operators_and_greek_are_spelled_out(self):
        from proofmotion.layout.notation import to_latex

        self.assertEqual(to_latex("sum ≈ 9.86"), r"sum \approx 9.86")
        self.assertEqual(to_latex("θ = 30°"), r"\theta = 30^{\circ}")

    def test_superscript_runs_collapse_into_one_group(self):
        """``x^{1}^{2}`` is a LaTeX error of its own."""
        from proofmotion.layout.notation import to_latex

        self.assertEqual(to_latex("x¹²"), "x^{12}")
        self.assertEqual(to_latex("∫₀³ x² dx"), r"\int_{0}^{3} x^{2} dx")

    def test_a_control_word_is_spaced_off_the_letter_after_it(self):
        """``\\Deltav`` is one undefined command — the same failure, translated."""
        from proofmotion.layout.notation import to_latex

        self.assertEqual(to_latex("Δv/Δt"), r"\Delta v/\Delta t")
        self.assertEqual(to_latex("ω = 2πf"), r"\omega = 2\pi f")

    def test_the_spacing_fix_does_not_split_the_command_itself(self):
        """A greedy control word with a lookahead backtracks into itself.

        The first attempt produced ``\\alph a`` — correct-looking, and a worse
        error than the one it replaced.
        """
        from proofmotion.layout.notation import to_latex

        self.assertEqual(to_latex("α+β≥γ"), r"\alpha+\beta\geq \gamma")
        self.assertNotIn(r"\alph ", to_latex("α"))

    def test_nothing_untranslatable_survives(self):
        from proofmotion.layout.notation import unsupported

        for text in ("Σ x² ≤ ∞", "∇·E = ρ/ε", "α+β≥γ", "∫₀³ x² dx = 9", "Riemann — 16"):
            with self.subTest(text=text):
                self.assertEqual(unsupported(text), [])

    def test_plain_text_is_left_alone(self):
        from proofmotion.layout.notation import to_latex

        self.assertEqual(to_latex("R_6 = 11.375"), "R_6 = 11.375")
        self.assertEqual(to_latex(""), "")

    def test_invisible_spaces_are_translated(self):
        """U+202F between a number and its unit took a render down.

        The character is invisible in every log and error message it appears
        in, so the failure named a file in vendored Manim instead.
        """
        from proofmotion.layout.notation import unsupported

        self.assertEqual(unsupported("speed 20\u202fm/s at 76.5\u00b0"), [])
        self.assertEqual(unsupported("a\u2009b\u00a0c\u200bd"), [])

    def test_prose_and_maths_are_told_apart(self):
        """MathTex sets an English sentence in italic maths with no spaces."""
        from proofmotion.layout.notation import looks_like_maths

        for maths in ("R_6 = 11.375", r"\int_0^3 x^2 dx = 9", "f(x)=x^2", "n=13", "x^{12}"):
            with self.subTest(maths=maths):
                self.assertTrue(looks_like_maths(maths))
        for prose in (
            "The parabola f(x) = x\u00b2, symmetric about the y-axis.",
            "A projectile launched at 76.5\u00b0 with speed 20 m/s follows a parabolic arc.",
            "Right Riemann sum with 8 rectangles",
        ):
            with self.subTest(prose=prose):
                self.assertFalse(looks_like_maths(prose))
        self.assertFalse(looks_like_maths(""))

    def test_a_prose_caption_is_set_as_text_not_maths(self):
        from proofmotion.compose import SceneAssignment, ScenePlan, assemble
        from proofmotion.tools.manim_api import manim_validate_code

        code = assemble(ScenePlan(assignments=[
            SceneAssignment(
                title="x", component="function_plot", parameters=PLOT,
                caption="A projectile launched at 76.5\u00b0 with speed 20 m/s follows a parabolic arc.",
            ),
        ]))
        self.assertIn("caption = Text(", code)
        self.assertNotIn("caption = MathTex(", code)
        self.assertEqual(manim_validate_code(code)["valid"], True)

    def test_the_assembler_translates_captions(self):
        """The caption reaches MathTex, which cannot compile any of this."""
        from proofmotion.compose import SceneAssignment, ScenePlan, assemble

        code = assemble(ScenePlan(assignments=[
            SceneAssignment(title="x", component="function_plot", parameters=PLOT, caption="sum ≈ 9.86"),
        ]))
        self.assertIn(r"\approx", code)
        self.assertNotIn("≈", code)


class TestOperations(unittest.TestCase):
    def test_add_places_after_the_named_slide(self):
        p = project(slide("s1"), slide("s2"))
        apply(p, Operation(kind="add", after="s1", title="new", component="function_plot", parameters=PLOT))
        self.assertEqual([s.id for s in p.slides], ["s1", "s3", "s2"])

    def test_add_without_after_appends(self):
        p = project(slide("s1"))
        apply(p, Operation(kind="add", title="new", component="function_plot", parameters=PLOT))
        self.assertEqual([s.id for s in p.slides], ["s1", "s2"])

    def test_set_parameter_leaves_the_others_alone(self):
        p = project(slide("s1", component="riemann_area",
                          parameters={"expr": "x**2", "a": 0, "b": 3, "rectangles": 6}))
        apply(p, Operation(kind="set_parameter", slide_id="s1", name="rectangles", value=24))
        self.assertEqual(p.slides[0].parameters, {"expr": "x**2", "a": 0, "b": 3, "rectangles": 24})

    def test_a_parameter_the_component_rejects_is_refused(self):
        """Caught while it is still an operation, not as a failing clip."""
        p = project(slide("s1"))
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="set_parameter", slide_id="s1", name="x_min", value="left"))

    def test_an_unknown_component_is_refused(self):
        p = project()
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="add", title="x", component="no_such_component", parameters={}))

    def test_an_empty_slide_is_refused(self):
        p = project()
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="add"))

    def test_a_locked_slide_cannot_be_edited(self):
        """The promise that makes a studio usable."""
        p = project(slide("s1", locked=True))
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="edit", slide_id="s1", title="overwritten"))
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="delete", slide_id="s1"))
        self.assertEqual(p.slides[0].title, "")

    def test_a_locked_slide_can_be_unlocked_then_edited(self):
        p = project(slide("s1", locked=True))
        apply(p, Operation(kind="lock", slide_id="s1", locked=False))
        apply(p, Operation(kind="edit", slide_id="s1", title="now fine"))
        self.assertEqual(p.slides[0].title, "now fine")

    def test_one_bad_operation_does_not_discard_the_rest(self):
        p = project(slide("s1"))
        outcome = apply_all(p, [
            Operation(kind="add", title="ok", component="function_plot", parameters=PLOT),
            Operation(kind="set_parameter", slide_id="s1", name="x_min", value="left"),
            Operation(kind="add", title="also ok", component="function_plot", parameters=PLOT),
        ])
        self.assertEqual(outcome["applied"], 2)
        self.assertEqual(len(outcome["refused"]), 1)
        self.assertEqual(len(p.slides), 3)

    def test_the_revision_moves_only_when_something_applied(self):
        p = project(slide("s1"))
        apply_all(p, [Operation(kind="set_parameter", slide_id="s1", name="x_min", value="left")])
        self.assertEqual(p.revision, 0)
        apply_all(p, [Operation(kind="edit", slide_id="s1", title="x")])
        self.assertEqual(p.revision, 1)

    def test_touched_reports_what_needs_re_rendering(self):
        self.assertEqual(
            touched([
                Operation(kind="edit", slide_id="s2"),
                Operation(kind="lock", slide_id="s3"),   # changes no pixels
                Operation(kind="add", title="x"),
            ]),
            ["s2"],
        )


if __name__ == "__main__":
    unittest.main()
