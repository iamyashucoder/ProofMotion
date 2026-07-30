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

    def test_one_figure_with_changing_numbers_stays_a_single_run(self):
        """So it can morph. This is where the motion comes from.

        Split into separate clips these become two pictures with a cut between
        — the static feel the studio was reported for. Together, the assembler
        transforms one into the other and the rectangles visibly narrow. The
        cost is a wider cache unit, taken deliberately.
        """
        runs = group([slide("s1"), slide("s2", parameters={**PLOT, "x_max": 5.0})])
        self.assertEqual([[x.id for x in r] for r in runs], [["s1", "s2"]])

    def test_a_different_component_starts_a_new_run(self):
        runs = group([slide("s1"), slide("s2", component="tangent_secant",
                                         parameters={**PLOT, "at": 3.0})])
        self.assertEqual(len(runs), 2)

    def test_a_hand_written_slide_never_shares_a_run(self):
        """It owns the whole frame; there is nothing to assemble around it."""
        runs = group([slide("s1"), Slide(id="s2", code="from manim import *"), slide("s3")])
        self.assertEqual([[x.id for x in r] for r in runs], [["s1"], ["s2"], ["s3"]])

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

    def test_editing_one_slide_leaves_the_other_units_alone(self):
        """One edit, one unit re-rendered — the claim, at unit granularity.

        Units widened when slides on one figure were grouped so they could
        morph, so the guarantee is per unit rather than per slide. Everything
        the edit did not touch still keeps its clip.
        """
        p = project(
            slide("s1", title="a"),
            slide("s2", title="b", component="tangent_secant", parameters={**PLOT, "at": 3.0}),
            slide("s3", title="c", component="riemann_area",
                  parameters={"expr": "x**2", "a": 0, "b": 3, "rectangles": 6}),
        )
        before = [u.digest for u in units_of(p)]
        self.assertEqual(len(before), 3, "three components, three units")
        apply(p, Operation(kind="edit", slide_id="s2", title="changed"))
        after = [u.digest for u in units_of(p)]
        self.assertEqual(before[0], after[0])
        self.assertEqual(before[2], after[2])
        self.assertNotEqual(before[1], after[1])

    def test_reordering_whole_units_re_renders_nothing(self):
        """Moving a figure past another figure is a re-cut, not a re-render.

        Reordering *within* a unit does change it, because the unit is now the
        animation and its order is what the animation does.
        """
        p = project(
            slide("s1", title="a"),
            slide("s2", title="b", component="tangent_secant", parameters={**PLOT, "at": 3.0}),
        )
        before = {u.digest for u in units_of(p)}
        apply(p, Operation(kind="reorder", slide_id="s1"))
        self.assertEqual([s.id for s in p.slides], ["s2", "s1"])
        self.assertEqual(before, {u.digest for u in units_of(p)})


class TestHandWrittenCode(unittest.TestCase):
    """Scene code reaches a slide from more than one place, so it is checked at use."""

    BROKEN = (
        "from manim import *\n"
        "\\nclass SquareToCircle(Scene):\n"
        "    def construct(self):\n"
        "        self.play(Transform(Square(), Circle()))\n"
    )

    def test_escaping_and_the_class_name_are_repaired(self):
        """Both are silent at render time and neither is worth losing work over."""
        from proofmotion.studio.operations import usable_code

        fixed = usable_code(self.BROKEN)
        self.assertNotIn("\\n", fixed)
        self.assertIn("class GeneratedScene(Scene):", fixed)
        self.assertNotIn("SquareToCircle", fixed)

    def test_a_missing_component_import_is_supplied(self):
        """`from manim import *` does not bring `build` in.

        The coder is shown component usage in its own brief, writes the call,
        and omits the import — which the validator correctly refuses, costing
        the whole slide for a mechanical omission.
        """
        from proofmotion.studio.operations import usable_code

        fixed = usable_code(
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            '        built = build("function_plot", {"expr": "x**2", "x_min": 0, "x_max": 3})\n'
            "        place(built.group, layout('title_stage_caption')['stage'])\n"
            "        self.play(FadeIn(built.group))\n"
        )
        self.assertIn("from proofmotion.components import build", fixed)
        self.assertIn("from proofmotion.layout.regions import place", fixed)

    def test_an_import_already_there_is_not_duplicated(self):
        from proofmotion.studio.operations import usable_code

        fixed = usable_code(
            "from manim import *\n"
            "from proofmotion.components import build\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            '        built = build("function_plot", {"expr": "x**2", "x_min": 0, "x_max": 3})\n'
            "        self.add(built.group)\n"
        )
        self.assertEqual(fixed.count("from proofmotion.components import build"), 1)

    def test_a_two_line_label_is_not_destroyed(self):
        """The repair was breaking working code.

        Text("pretrained\\nknowledge") is a two-line label and entirely valid.
        A blanket replace of backslash-n turned its escape into a real newline,
        left the string literal unterminated, and reported "the scene does not
        parse" about source that had parsed perfectly a moment earlier.
        """
        from proofmotion.studio.operations import usable_code

        source = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            '        self.add(Text("pretrained\\nknowledge"))\n'
        )
        import ast

        ast.parse(source)  # valid before
        fixed = usable_code(source)
        ast.parse(fixed)  # and after
        self.assertIn("pretrained", fixed)

    def test_code_that_cannot_render_is_refused_with_a_reason(self):
        from proofmotion.studio.operations import usable_code

        for label, source in (
            ("empty", "   "),
            ("no scene", "x = 1"),
            ("bad api", (
                "from manim import *\nclass GeneratedScene(Scene):\n"
                "    def construct(self):\n        self.add(Dot(color=MAGENTA))\n"
            )),
        ):
            with self.subTest(label=label), self.assertRaises(ToolError):
                usable_code(source)

    def test_a_slide_stored_before_the_check_existed_still_renders(self):
        """Normalising only on write leaves old documents broken forever.

        A project written by an earlier version carries the literal escape and
        the wrong class name, and would fail on every render for its whole
        life. The repair belongs at the point of use.
        """
        from proofmotion.studio.render import units_of

        p = project(Slide(id="s1", title="Square to Circle", code=self.BROKEN))
        unit = units_of(p)[0]
        self.assertEqual(unit.ids, ["s1"])
        # The document keeps exactly what was stored; the renderer copes.
        self.assertIn("SquareToCircle", p.slides[0].code)


class TestRemakeStaysOnItsSlide(unittest.TestCase):
    """A remake names a slide, and drawing has to honour that.

    draw_by_hand always emitted `add`, so asking to redraw slide one produced a
    second slide beside it with the one complained about still there — and
    asking again produced a third.
    """

    SCENE = (
        "from manim import *\n"
        "class GeneratedScene(Scene):\n"
        "    def construct(self):\n"
        "        self.add(Dot())\n"
    )

    def test_redrawing_replaces_rather_than_appends(self):
        p = project(Slide(id="s1", title="LoRA", code="from manim import *\n"
                          "class GeneratedScene(Scene):\n"
                          "    def construct(self):\n        self.add(Square())\n"))
        apply_all(p, [Operation(kind="edit", slide_id="s1", title="Redrawn",
                                code=self.SCENE, reason="redrawn by hand")])
        self.assertEqual([s.id for s in p.slides], ["s1"])
        self.assertIn("Dot()", p.slides[0].code)

    def test_draw_by_hand_edits_when_given_a_slide(self):
        """The operation kind is what carries the difference."""
        import inspect

        from proofmotion.studio.compose_full import draw_by_hand

        self.assertIn("replacing", inspect.signature(draw_by_hand).parameters)


class TestStudioStartup(unittest.TestCase):
    def test_launching_opens_a_fresh_project(self):
        """Resuming meant the first slide you added came back as s14.

        Reopening the last deck costs nothing, since every clip is cached — but
        it drops you into yesterday's work when you asked for a studio, and the
        numbering carries on from a deck you were not looking at.
        """
        import tempfile
        from pathlib import Path

        from proofmotion.web.studio import Studio

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            old = Project.create("yesterday", "an old question")
            old.slides = [Slide(id=f"s{i}") for i in range(1, 14)]
            old.save(root / "yesterday")

            studio = Studio(root, client=None)
            self.assertNotEqual(studio.current, "yesterday")
            self.assertEqual(studio.load().next_id(), "s1")
            # And the old one is still one click away.
            self.assertEqual([p["id"] for p in studio.listing()], ["yesterday"])

    def test_an_untouched_new_project_is_not_written_to_disk(self):
        """Or every launch would leave an empty deck behind in the explorer."""
        import tempfile
        from pathlib import Path

        from proofmotion.web.studio import Studio

        with tempfile.TemporaryDirectory() as tmp:
            studio = Studio(Path(tmp), client=None)
            self.assertEqual(studio.listing(), [])


class TestOverrides(unittest.TestCase):
    """Hand corrections, because a checker cannot know what reads better.

    inspect_scene can measure that a label overlaps a curve. It cannot know the
    label reads better slightly left, and until now there was nowhere for a
    person to say so.
    """

    def test_a_nudge_is_recorded_on_the_slide(self):
        p = project(slide("s1"))
        apply(p, Operation(kind="nudge", slide_id="s1", name="caption",
                           value={"shift": {"dx": -0.4, "dy": 0.15}}))
        self.assertEqual(p.slides[0].overrides["shift"]["caption"], {"dx": -0.4, "dy": 0.15})

    def test_nudges_accumulate_across_objects(self):
        p = project(slide("s1"))
        apply(p, Operation(kind="nudge", slide_id="s1", name="caption", value={"shift": {"dx": -0.4}}))
        apply(p, Operation(kind="nudge", slide_id="s1", name="title", value={"shift": {"dy": 0.2}}))
        self.assertEqual(sorted(p.slides[0].overrides["shift"]), ["caption", "title"])

    def test_a_nudge_needs_something_to_move(self):
        p = project(slide("s1"))
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="nudge", slide_id="s1", value={"shift": {"dx": 1}}))

    def test_a_locked_slide_refuses_a_nudge(self):
        p = project(slide("s1", locked=True))
        with self.assertRaises(ToolError):
            apply(p, Operation(kind="nudge", slide_id="s1", name="caption", value={"shift": {"dx": 1}}))

    def test_an_override_reaches_the_emitted_scene(self):
        from proofmotion.compose import SceneAssignment, ScenePlan, assemble
        from proofmotion.tools.manim_api import manim_validate_code

        code = assemble(ScenePlan(assignments=[SceneAssignment(
            title="T", component="function_plot", parameters=PLOT, caption="f(x)=x^2",
            overrides={"shift": {"caption": {"dx": -0.4, "dy": 0.15}}, "scale": {"caption": 0.9}},
        )]))
        self.assertIn("caption.shift(RIGHT * -0.4 + UP * 0.15)", code)
        self.assertIn("caption.scale(0.9)", code)
        self.assertEqual(manim_validate_code(code)["valid"], True)

    def test_a_nudge_re_renders_the_slide(self):
        """It changes the pixels, so it has to change the cache key."""
        plain = slide("s1")
        nudged = slide("s1")
        nudged.overrides = {"shift": {"caption": {"dx": -0.4}}}
        self.assertNotEqual(digest_of([plain]), digest_of([nudged]))


class TestReveal(unittest.TestCase):
    """How a piece of a figure arrives, which is most of whether it feels alive.

    Every beat played FadeIn, so everything blinked into existence at full
    opacity — a curve that appears has no more life than a photograph of one,
    and thirty-two of thirty-four components only ever appeared.
    """

    def animation(self, mobject):
        from manim import tempconfig

        from proofmotion.layout.reveal import reveal

        with tempconfig({"dry_run": True}):
            return type(reveal(mobject)).__name__

    def test_a_curve_is_drawn(self):
        from manim import Line, tempconfig

        with tempconfig({"dry_run": True}):
            self.assertEqual(self.animation(Line([0, 0, 0], [1, 1, 0])), "Create")

    def test_text_is_written(self):
        from manim import MathTex, Text, tempconfig

        with tempconfig({"dry_run": True}):
            self.assertEqual(self.animation(Text("hello")), "Write")
            self.assertEqual(self.animation(MathTex("x^2")), "Write")

    def test_a_group_reveals_its_parts_in_sequence(self):
        """A diagram should look assembled, not pasted."""
        from manim import Line, VGroup, tempconfig

        with tempconfig({"dry_run": True}):
            group = VGroup(Line([0, 0, 0], [1, 0, 0]), Line([0, 0, 0], [0, 1, 0]))
            self.assertEqual(self.animation(group), "AnimationGroup")

    def test_stroke_width_stored_per_point_does_not_raise(self):
        """`width or 0` on a numpy array is ambiguous, three frames into a render."""
        from manim import Circle, tempconfig

        from proofmotion.layout.reveal import _has_stroke

        with tempconfig({"dry_run": True}):
            self.assertIsInstance(_has_stroke(Circle()), bool)

    def test_the_assembler_draws_instead_of_fading(self):
        from proofmotion.compose import SceneAssignment, ScenePlan, assemble
        from proofmotion.tools.manim_api import manim_validate_code

        code = assemble(ScenePlan(assignments=[
            SceneAssignment(title="T", component="function_plot", parameters=PLOT, seconds=8),
        ]))
        self.assertIn("reveal_all(parts", code)
        self.assertNotIn("FadeIn(p) for p in parts", code)
        self.assertEqual(manim_validate_code(code)["valid"], True)


class TestPhysicsMotions(unittest.TestCase):
    """Four components that now move, each through its own physics."""

    def built(self, name, params):
        from manim import tempconfig

        from proofmotion.components import build as build_component

        with tempconfig({"dry_run": True}):
            return build_component(name, params)

    def test_each_one_carries_a_motion_that_constructs(self):
        from manim import tempconfig

        for name, params in (
            ("pendulum", {"length": 1.0, "angle_deg": 25}),
            ("spring_mass", {"mass": 1, "stiffness": 10, "displacement": 1.0}),
            ("wave_form", {"amplitude": 1, "wavelength": 2, "cycles": 3}),
            ("vector_field", {"x_component": "-y", "y_component": "x"}),
        ):
            with self.subTest(component=name):
                built = self.built(name, params)
                self.assertTrue(built.motions, f"{name} still stands still")
                with tempconfig({"dry_run": True}):
                    self.assertIsNotNone(built.motions[0]())

    def test_the_pendulum_withdraws_its_force_arrows_before_swinging(self):
        """An arrow labelled mg that does not point down is a lie.

        Carrying the vectors round with the bob would be worse than not moving
        at all, so they belong to the displaced position and are faded for the
        duration of the swing.
        """
        from manim import tempconfig

        built = self.built("pendulum", {"length": 1.0, "angle_deg": 25})
        with tempconfig({"dry_run": True}):
            swing = built.motions[0]()
        # FadeOut, two rotations, FadeIn.
        self.assertEqual(len(swing.animations), 4)

    def test_the_angle_mark_is_withdrawn_too(self):
        """It marks the displaced angle, so it is as wrong mid-swing as mg is.

        Turning show_forces off does not change this: the arc is still there
        and still describes a position the bob has left.
        """
        from manim import tempconfig

        built = self.built("pendulum", {"length": 1.0, "angle_deg": 25, "show_forces": False})
        self.assertIn("angle", built.parts)
        with tempconfig({"dry_run": True}):
            swing = built.motions[0]()
        self.assertEqual(len(swing.animations), 4)

    def test_a_streamline_follows_the_field_and_stops_at_the_edge(self):
        """A tracer must never reappear somewhere it did not flow to."""
        from proofmotion.components.core import _streamline

        trail = _streamline(lambda x, y: 1.0, lambda x, y: 0.0, 0.0, 0.0, extent=2.0)
        self.assertGreater(len(trail), 3)
        self.assertTrue(all(abs(x) <= 2.0 and abs(y) <= 2.0 for x, y in trail))

    def test_a_field_that_vanishes_yields_no_tracer(self):
        from proofmotion.components.core import _streamline

        self.assertEqual(len(_streamline(lambda x, y: 0.0, lambda x, y: 0.0, 0.0, 0.0, 2.0)), 1)


class TestNeuralNetwork(unittest.TestCase):
    """A network with the data actually crossing it."""

    def built(self, params):
        from manim import tempconfig

        from proofmotion.components import build as build_component

        with tempconfig({"dry_run": True}):
            return build_component("neural_network", params)

    def test_the_activation_flows(self):
        built = self.built({"layers": [3, 5, 5, 2], "labels": ["x", "h", "h", "y"], "highlight": "x"})
        self.assertTrue(built.motions)
        self.assertIn("edges", built.parts)
        self.assertIn("units", built.parts)

    def test_the_weight_count_is_the_real_one(self):
        built = self.built({"layers": [3, 5, 5, 2]})
        self.assertIn("50 weights", built.notes)  # 3*5 + 5*5 + 5*2

    def test_a_two_layer_network_still_flows(self):
        from manim import tempconfig

        built = self.built({"layers": [2, 2]})
        with tempconfig({"dry_run": True}):
            self.assertIsNotNone(built.motions[0]())


class TestPreamble(unittest.TestCase):
    def test_a_package_that_is_not_installed_is_never_added(self):
        """One missing package fails every compile, not just the ones using it.

        Adding three of them blind broke "a = 4.9", which had nothing to do
        with any of them.
        """
        from proofmotion.layout.preamble import installed

        self.assertFalse(installed("definitely_not_a_real_package_xyz"))


class TestMotionComponents(unittest.TestCase):
    """Components where something happens, rather than a picture of it.

    Every component drew a state, and beats only reveal the pieces of a state,
    so a question about a ball bouncing got a picture of a ball. Convergence and
    divergence look identical in a table of numbers and obvious on a graph,
    which is the entire reason to draw them.
    """

    def build(self, name, params):
        from manim import tempconfig

        from proofmotion.components import build as build_component

        with tempconfig({"dry_run": True}):
            return build_component(name, params)

    def test_a_bouncing_ball_actually_moves(self):
        built = self.build("bouncing_trajectory", {"height": 8, "ratio": 0.75, "bounces": 5})
        self.assertTrue(built.motions, "a bouncing ball with no motion is a picture of a ball")
        self.assertIn("ball", built.parts)
        self.assertIn("path", built.parts)

    def test_the_heights_are_the_geometric_sequence(self):
        """The arcs are drawn from the numbers, so the two cannot disagree."""
        built = self.build("bouncing_trajectory", {"height": 8, "ratio": 0.75, "bounces": 4})
        for expected in ("8", "6", "4.5", "3.38"):
            self.assertIn(expected, built.notes)

    def test_a_rebound_above_one_is_reported_as_unbounded(self):
        built = self.build("bouncing_trajectory", {"height": 8, "ratio": 1.05, "bounces": 5})
        self.assertIn("without bound", built.notes)

    def test_partial_sums_are_computed_not_taken_on_trust(self):
        built = self.build("partial_sums", {"terms": [8, 12, 9, 6.75], "limit": 56})
        self.assertIn("8.00, 20.00, 29.00, 35.75", built.notes)
        self.assertTrue(built.motions)
        self.assertIn("limit", built.parts)

    def test_divergence_says_so_instead_of_drawing_a_limit(self):
        built = self.build("partial_sums", {"terms": [8, 8.4, 8.82, 9.26]})
        self.assertIn("diverges", built.parts)
        self.assertNotIn("limit", built.parts)

    def test_the_assembler_plays_what_a_component_moves(self):
        """A motion nothing plays is a motion that did not happen."""
        from proofmotion.compose import SceneAssignment, ScenePlan, assemble
        from proofmotion.tools.manim_api import manim_validate_code

        code = assemble(ScenePlan(assignments=[
            SceneAssignment(title="Bounce", component="bouncing_trajectory",
                            parameters={"height": 8, "ratio": 0.75, "bounces": 5}, seconds=9),
        ]))
        self.assertIn("for motion in built.motions", code)
        self.assertEqual(manim_validate_code(code)["valid"], True)


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

    def test_latex_commands_decide_the_mobject(self):
        """The gibberish that reached finished videos.

        ``x\\text{-axis: down the incline}`` has three ordinary words in it, so
        a prose-first rule sent correct LaTeX to Text — which cannot set it and
        draws the backslashes instead.
        """
        from proofmotion.layout.notation import looks_like_maths

        for latex in (
            r"x\text{-axis: down the incline}",
            r"\sum F_x = mg\sin\theta = m a",
            r"a = (9.8\,\text{m/s}^2)\sin 30^\circ",
            r"\vec{W} = m\vec{g}",
        ):
            with self.subTest(latex=latex):
                self.assertTrue(looks_like_maths(latex), "LaTeX must go to MathTex")

    def test_latex_reads_back_as_mathematics(self):
        """The chat had been showing raw source, with no renderer to set it."""
        from proofmotion.layout.notation import readable

        self.assertEqual(readable(r"\theta = 30^\circ"), "θ = 30°")
        self.assertEqual(readable(r"\int_{0}^{3} x^{2}\,dx = 9"), "∫₀³ x² dx = 9")
        self.assertEqual(readable(r"R_{6} = 11.375"), "R₆ = 11.375")
        self.assertEqual(readable(r"\vec{W} = m\vec{g}"), "W = mg")
        self.assertEqual(readable(""), "")
        for latex in (r"\sum F_x = mg\sin\theta", r"\frac{1}{2}mv^2"):
            with self.subTest(latex=latex):
                self.assertNotIn("\\", readable(latex))

    def test_axis_labels_stop_being_digits_when_nobody_could_read_them(self):
        """An exponential to x=15 labelled its ticks 3300000.0."""
        from proofmotion.components.graphs import compact, tick_decimals

        self.assertEqual(tick_decimals(10), 0)
        self.assertEqual(tick_decimals(0.05), 2)
        self.assertEqual(compact(800000), r"8 \times 10^{5}")
        self.assertEqual(compact(0.00042), r"4.2 \times 10^{-4}")
        # An ordinary axis stays ordinary.
        self.assertEqual(compact(12.5), "12.5")
        self.assertEqual(compact(3), "3")
        self.assertEqual(compact(0), "0")

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

    def test_a_chain_of_adds_lands_in_order(self):
        """The agent cannot know the id of a slide it is adding this turn.

        Asked for four slides it invented slide_1..slide_4 to chain them and
        three of the four were refused for naming slides that never existed.
        Chaining was exactly what it meant; the ids were the only thing wrong.
        """
        p = project()
        out = apply_all(p, [
            Operation(kind="add", title="one", component="function_plot", parameters=PLOT),
            Operation(kind="add", after="slide_1", title="two", component="function_plot", parameters=PLOT),
            Operation(kind="add", after="slide_2", title="three", component="function_plot", parameters=PLOT),
        ])
        self.assertEqual(out["applied"], 3)
        self.assertEqual(out["refused"], [])
        self.assertEqual([s.title for s in p.slides], ["one", "two", "three"])

    def test_a_real_slide_named_in_after_is_still_honoured(self):
        p = project(slide("s1", title="first"), slide("s2", title="last"))
        apply_all(p, [Operation(kind="add", after="s1", title="middle",
                                component="function_plot", parameters=PLOT)])
        self.assertEqual([s.title for s in p.slides], ["first", "middle", "last"])

    def test_a_full_answer_fits_in_one_edit(self):
        """Two ceilings that did not know about each other.

        A storyboard may hold MAX_SCENES scenes and a full derivation emits one
        `add` per scene, but the operation list was capped at a hand-picked 20 —
        so a valid 23-slide answer was rejected outright by its own schema.
        """
        from proofmotion.studio.operations import MAX_OPERATIONS, Edit
        from schemas.storyboard import MAX_SCENES

        self.assertGreaterEqual(MAX_OPERATIONS, MAX_SCENES)
        full = Edit(operations=[Operation(kind="add", title=f"scene {i}") for i in range(MAX_SCENES)])
        self.assertEqual(len(full.operations), MAX_SCENES)

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
