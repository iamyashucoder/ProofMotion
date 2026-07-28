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

from manim import config, tempconfig
from pydantic import ValidationError

from proofmotion.components import COMPONENTS, build
from proofmotion.layout.collision import bounds, major_collisions, text_on_ink
from proofmotion.layout.labels import place_label
from proofmotion.layout.regions import LAYOUT_NAMES, layout, place


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


class RegistrationTests(unittest.TestCase):
    """Registration happens as an import side effect, which a linter once undid.

    `ruff --fix` deleted components_tool from the package imports as unused,
    silently removing component_search and component_build. Nothing failed until
    an agent asked for the toolset mid-run.
    """

    def test_every_toolset_resolves(self):
        from proofmotion.tools import TOOLSETS, toolset

        for group in TOOLSETS:
            self.assertTrue(toolset(group).names, f"{group} resolved to nothing")

    def test_component_tools_are_registered(self):
        from proofmotion.tools import REGISTRY

        for name in ("component_search", "component_build"):
            self.assertIn(name, REGISTRY.names, f"{name} is missing from the registry")

    def test_competitive_math_visuals_are_registered(self):
        for name in ("number_line_marks", "unit_circle", "geometry_construction", "matrix_transform", "distribution_plot"):
            self.assertIn(name, COMPONENTS)

    def test_meter_scale_friction_visual_is_registered(self):
        self.assertIn("meter_scale_friction", COMPONENTS)


class CodeRecoveryTests(unittest.TestCase):
    """A run once failed with "the coding agent returned no code" while the agent
    had already validated a working scene. The source was in its tool calls."""

    SCENE = "from manim import *\nclass GeneratedScene(Scene):\n    def construct(self):\n        self.add(Dot())\n"

    def test_recovers_the_last_validated_scene(self):
        import json as _json

        from proofmotion.agents.coder import recover_code

        calls = [
            {"name": "manim_search", "arguments": '{"query": "dot"}', "failed": False},
            {"name": "manim_validate_code", "arguments": _json.dumps({"code": self.SCENE}), "failed": False},
        ]
        self.assertIn("GeneratedScene", recover_code(calls))

    def test_skips_unparseable_and_unrelated_calls(self):
        import json as _json

        from proofmotion.agents.coder import recover_code

        calls = [
            {"name": "inspect_scene", "arguments": _json.dumps({"code": "def broken("}), "failed": True},
            {"name": "manim_search", "arguments": "not json at all", "failed": False},
        ]
        self.assertEqual(recover_code(calls), "")

    def test_truncated_source_is_not_treated_as_usable(self):
        """The failure this was written for, and the one it originally missed.

        A scene cut off mid-call still contains "GeneratedScene", so checking for
        the class name alone let unparseable source straight through.
        """
        from proofmotion.agents.coder import _usable

        truncated = (
            "from manim import *\nclass GeneratedScene(Scene):\n"
            "    def construct(self):\n        self.play(AnimationGroup("
        )
        self.assertFalse(_usable(truncated))
        self.assertTrue(_usable(self.SCENE))

    def test_prefers_the_most_recent_scene(self):
        import json as _json

        from proofmotion.agents.coder import recover_code

        newer = self.SCENE.replace("Dot()", "Square()")
        calls = [
            {"name": "manim_validate_code", "arguments": _json.dumps({"code": self.SCENE}), "failed": False},
            {"name": "inspect_scene", "arguments": _json.dumps({"code": newer}), "failed": False},
        ]
        self.assertIn("Square()", recover_code(calls))


class ResponsesFallbackTests(unittest.TestCase):
    """gpt-5.6 refuses function tools on chat-completions and names the fix.

    The switch works, but it used to announce itself with an ERROR line for a
    condition that was immediately handled, which reads as a failed run.
    """

    def test_a_handled_switch_is_not_logged_as_an_error(self):
        import types

        from llm.providers import LLMError, OpenAIClient

        client = OpenAIClient("gpt-5.6-terra")
        refusal = (
            "Error code: 400 - Function tools with reasoning_effort are not supported for "
            "gpt-5.6-terra in /v1/chat/completions. To use function tools, use /v1/responses"
        )

        def refuse(*args, **kwargs):
            raise LLMError(refusal)

        switched = {}

        class FakeDelegate:
            def chat(self, messages, *, tools=None, max_tokens=4000):
                switched["yes"] = True
                return types.SimpleNamespace(content="ok", tool_calls=None)

        from llm import providers

        original_super, original_delegate = providers.OpenAICompatibleClient.chat, providers.OpenAIResponsesClient
        providers.OpenAICompatibleClient.chat = refuse
        providers.OpenAIResponsesClient = lambda *a, **k: FakeDelegate()
        try:
            with self.assertLogs("llm.providers", level="DEBUG") as captured:
                client.chat([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
        finally:
            providers.OpenAICompatibleClient.chat = original_super
            providers.OpenAIResponsesClient = original_delegate

        self.assertTrue(switched.get("yes"), "should have switched to the Responses delegate")
        self.assertFalse(
            [line for line in captured.output if line.startswith("ERROR")],
            f"a recovered switch must not log ERROR: {captured.output}",
        )

    def test_an_unrelated_failure_still_propagates(self):
        from llm import providers
        from llm.providers import LLMError, OpenAIClient

        def refuse(*args, **kwargs):
            raise LLMError("Error code: 500 - the server is on fire")

        client = OpenAIClient("gpt-5.6-terra")
        client._responses_delegate = None
        OpenAIClient._needs_responses.discard("gpt-5.6-terra")
        original = providers.OpenAICompatibleClient.chat
        providers.OpenAICompatibleClient.chat = refuse
        try:
            with self.assertRaises(LLMError):
                client.chat([{"role": "user", "content": "hi"}], tools=[{"type": "function"}])
        finally:
            providers.OpenAICompatibleClient.chat = original


class MissingReturnTests(unittest.TestCase):
    """A helper that builds a mobject and forgets to return it.

    The caller gets None and the failure surfaces far away — always_redraw
    reporting that NoneType has no add_updater, with the traceback pointing at
    the caller rather than the helper that is actually wrong.
    """

    BROKEN = (
        "from manim import *\n"
        "class GeneratedScene(Scene):\n"
        "    def construct(self):\n"
        "        def make_letter(letter, color):\n"
        "            txt = Text(letter, color=color)\n"
        "            grp = VGroup(txt)\n"
        "        P = make_letter('P', WHITE)\n"
        "        self.play(FadeIn(P))\n"
    )

    def test_a_helper_without_a_return_is_flagged(self):
        from proofmotion.tools.manim_api import manim_validate_code

        report = manim_validate_code(self.BROKEN)
        self.assertFalse(report["valid"])
        self.assertIn("never returns a value", report["problems"][0]["problem"])

    def test_adding_the_return_clears_it(self):
        from proofmotion.tools.manim_api import manim_validate_code

        fixed = self.BROKEN.replace("            grp = VGroup(txt)", "            grp = VGroup(txt)\n            return grp")
        self.assertTrue(manim_validate_code(fixed)["valid"])

    def test_a_procedure_that_is_meant_to_return_nothing_is_not_flagged(self):
        """reveal() only plays; returning nothing is correct, not a defect."""
        from proofmotion.tools.manim_api import manim_validate_code

        procedure = (
            "from manim import *\n"
            "class GeneratedScene(Scene):\n"
            "    def construct(self):\n"
            "        def reveal(mob):\n"
            "            self.play(FadeIn(mob))\n"
            "        d = Dot()\n"
            "        reveal(d)\n"
        )
        self.assertTrue(manim_validate_code(procedure)["valid"])

    def test_scenes_that_rendered_are_not_flagged(self):
        from pathlib import Path

        from proofmotion.tools.manim_api import manim_validate_code

        rendered = [
            p for p in Path("generated_projects").glob("*/generated_scene.py")
            if p.stat().st_size and (p.parent / "preview").exists()
            and any("partial_movie_files" not in v.parts for v in (p.parent / "preview").rglob("*.mp4"))
        ]
        if not rendered:
            self.skipTest("no rendered projects available")
        for scene in rendered:
            voids = [
                x for x in manim_validate_code(scene.read_text(encoding="utf-8"))["problems"]
                if "never returns a value" in x.get("problem", "")
            ]
            self.assertEqual(voids, [], f"false positive in {scene}")


class DirectWriteFallbackTests(unittest.TestCase):
    """An agent can explore its whole budget and hand back nothing.

    One run spent 41 tool calls without ever passing code to a tool, so there was
    nothing to recover and the pipeline failed with "returned no code" — while
    the model had simply never been asked plainly.
    """

    SCENE = "from manim import *\nclass GeneratedScene(Scene):\n    def construct(self):\n        self.add(Dot())\n"

    def _stub(self, tool_reply, plain_reply):
        import types

        class Stub:
            name = model = "stub"

            def chat(self, messages, *, tools=None, max_tokens=4000):
                content = tool_reply if tools else plain_reply
                return types.SimpleNamespace(content=content, tool_calls=None)

        return Stub()

    def test_a_scene_is_recovered_when_the_tool_loop_yields_nothing(self):
        from proofmotion.agents.coder import write_scene

        out = write_scene(self._stub("I explored thoroughly.", self.SCENE),
                          {"intent": {"duration_seconds": 30}}, max_iterations=3)
        self.assertIn("GeneratedScene", out["code"])
        self.assertTrue(out["wrote_directly"])
        self.assertTrue(out["validation"]["valid"])

    def test_a_hopeless_run_still_reports_failure(self):
        """The fallback must not turn "no code" into a false success."""
        from proofmotion.agents.coder import write_scene

        out = write_scene(self._stub("I cannot.", "I cannot."),
                          {"intent": {"duration_seconds": 30}}, max_iterations=2)
        self.assertFalse(out["validation"]["valid"])
        self.assertTrue(out["wrote_directly"])


class FilledShapeInkTests(unittest.TestCase):
    """The inside of a filled shape is ink, and the checker was blind to it.

    Ink was the sampled points of a mobject's outline, and a filled disc has
    points only on its rim. So "frictionless axle" lay unreadable across a disc
    in a finished video while the checker measured zero overlaps — steering the
    whole system on a metric that reported success on the frames being
    complained about.
    """

    def collide(self, *mobjects) -> list:
        from manim import VGroup

        with tempconfig({"dry_run": True}):
            return major_collisions([VGroup(*mobjects)])

    def test_a_label_lying_across_a_filled_shape_is_caught(self):
        from manim import Circle, Text

        with tempconfig({"dry_run": True}):
            disc = Circle(radius=2.0, color="#4aa3df", fill_opacity=0.35)
            label = Text("frictionless axle", font_size=24).move_to(disc.get_center())
        self.assertTrue(self.collide(disc, label), "text on a fill went unreported")

    def test_the_same_label_inside_an_unfilled_outline_is_clean(self):
        """Nothing is drawn there, so the text is perfectly readable."""
        from manim import Circle, Text

        with tempconfig({"dry_run": True}):
            hollow = Circle(radius=2.0, color="#4aa3df", fill_opacity=0.0)
            label = Text("readable", font_size=24).move_to(hollow.get_center())
        self.assertEqual(self.collide(hollow, label), [])

    def test_a_hole_in_a_ring_is_not_ink(self):
        """Subpaths matter: joining them makes a ring measure as solid."""
        from manim import Annulus, Text

        with tempconfig({"dry_run": True}):
            ring = Annulus(inner_radius=1.2, outer_radius=2.0, fill_opacity=1.0)
            in_hole = Text("hole", font_size=22).move_to(ring.get_center())
            on_band = Text("band", font_size=18).move_to([1.6, 0, 0])
        self.assertEqual(self.collide(ring, in_hole), [])
        self.assertTrue(self.collide(ring, on_band))

    def test_a_faint_wash_is_not_ink(self):
        from manim import Circle, Text

        with tempconfig({"dry_run": True}):
            wash = Circle(radius=2.0, fill_opacity=0.05)
            label = Text("still legible", font_size=24).move_to(wash.get_center())
        self.assertEqual(self.collide(wash, label), [])

    def test_a_background_rectangle_is_not_ink(self):
        """It exists to sit under a label; its border hugs the text.

        This was a false positive before any of the fill work — the outline
        alone landed inside the clearance box, so every boxed label read as a
        major collision.
        """
        from manim import BackgroundRectangle, Text

        with tempconfig({"dry_run": True}):
            label = Text("boxed", font_size=24)
            backdrop = BackgroundRectangle(label)
        self.assertEqual(self.collide(backdrop, label), [])

    def test_a_component_can_declare_a_shape_that_holds_text(self):
        """Geometry cannot tell a container from an accident.

        An array cell holding its value and a stray label on a filled disc are
        the same picture to a measuring tool, and at the same size ratio — 25.1
        against 24.2. So the component says which it is, and only a component
        can: raw scene code never sets this.
        """
        from manim import Square, Text

        from proofmotion.layout.collision import holds_text

        with tempconfig({"dry_run": True}):
            box = Square(side_length=0.9, fill_opacity=0.35)
            value = Text("7", font_size=24).move_to(box.get_center())
            self.assertTrue(self.collide(box, value), "an undeclared fill should still be ink")
            holds_text(box)
        self.assertEqual(self.collide(box, value), [])

    def test_the_library_declares_the_containers_it_uses(self):
        """array_cells and free_body_diagram write inside their own shapes."""
        with tempconfig({"dry_run": True}):
            cells = build("array_cells", {"values": [1, 3, 5, 7], "pointers": {"low": 0}})
            body = build("free_body_diagram", {"forces": [{"label": "mg", "magnitude": 9.8, "angle_deg": 270}]})
        self.assertEqual(major_collisions([cells.group]), [])
        self.assertEqual(major_collisions([body.group]), [])


class PointerStackingTests(unittest.TestCase):
    """low, mid and high on nearby cells used to overprint into one smear."""

    def _text_overlaps(self, group):
        from proofmotion.layout.collision import bounds, text_units

        boxes = [bounds(u) for u in text_units(group) if float(getattr(u, "width", 0))]
        return sum(
            1
            for i, a in enumerate(boxes)
            for b in boxes[i + 1 :]
            if min(a[1], b[1]) - max(a[0], b[0]) > 0.02 and min(a[3], b[3]) - max(a[2], b[2]) > 0.02
        )

    def test_pointers_never_overprint_however_close(self):
        for label, params in [
            ("distinct", dict(values=[1, 3, 5, 7, 9, 11, 13], pointers={"low": 0, "mid": 3, "high": 6})),
            ("two share a cell", dict(values=[1, 3, 5, 7, 9, 11, 13], pointers={"low": 0, "mid": 5, "high": 5})),
            ("all on one cell", dict(values=list(range(15)), pointers={"low": 10, "mid": 10, "high": 10})),
            ("adjacent cells", dict(values=list(range(15)), pointers={"low": 7, "mid": 8, "high": 9})),
            ("long names", dict(values=list(range(8)), pointers={"left": 2, "middle": 3, "right": 4})),
        ]:
            with self.subTest(case=label), tempconfig({"dry_run": True}):
                self.assertEqual(self._text_overlaps(build("array_cells", params).group), 0)


class ParallelDispatchTests(unittest.TestCase):
    def test_manim_config_tools_are_never_parallelised(self):
        """tempconfig mutates global renderer state; two at once corrupt both."""
        from proofmotion.runtime.loop import PARALLEL_SAFE

        for unsafe in ("inspect_scene", "component_build", "typeset_check", "layout_measure"):
            self.assertNotIn(unsafe, PARALLEL_SAFE)
        for safe in ("manim_signature", "symbolic_differentiate", "numeric_sample"):
            self.assertIn(safe, PARALLEL_SAFE)


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
            self.assertEqual(major_collisions([axes, curve, scored]), [])

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
        "pendulum": [
            dict(length=1.0, angle_deg=25), dict(length=0.25, angle_deg=5),
            dict(length=4.0, angle_deg=80, show_forces=False),
        ],
        "spring_mass": [
            dict(mass=1, stiffness=10, displacement=1), dict(mass=4, stiffness=1, displacement=-2),
            dict(mass=0.5, stiffness=100, displacement=2.5),
        ],
        "collision": [
            dict(mass_a=1, mass_b=1, velocity_a=3, velocity_b=-1),
            dict(mass_a=5, mass_b=1, velocity_a=2, velocity_b=0, kind="inelastic"),
            dict(mass_a=1, mass_b=9, velocity_a=4, velocity_b=0),
        ],
        "orbit": [
            dict(eccentricity=0.0), dict(eccentricity=0.6, body_angle_deg=150),
            dict(semi_major=3.0, eccentricity=0.9),
        ],
        "torque_diagram": [dict(angle_deg=90), dict(angle_deg=30, force=25), dict(angle_deg=175, lever_arm=0.5)],
        "standing_wave": [dict(harmonic=n) for n in (1, 2, 3, 5, 8)],
        "circuit_diagram": [
            dict(voltage=9, resistances=[100, 220]),
            dict(voltage=12, resistances=[10, 10, 10], arrangement="parallel"),
            dict(voltage=5, resistances=[1000]),
        ],
        # object_distance inside the focal length gives a virtual image, which is
        # drawn on the other side and must be reported as virtual.
        "ray_diagram": [
            dict(focal_length=1.5, object_distance=3), dict(focal_length=1.5, object_distance=1.0),
            dict(focal_length=-2.0, object_distance=3), dict(focal_length=2.0, object_distance=6),
        ],
        "field_lines": [
            dict(charges=[[-1, 0, 1], [1, 0, -1]]), dict(charges=[[0, 0, 1]]),
            dict(charges=[[-1, 0, 1], [1, 0, 1]]),
        ],
        "pv_diagram": [
            dict(states=[[3, 1], [1, 3], [1, 1]]), dict(states=[[1, 1], [3, 1], [3, 3], [1, 3]]),
            dict(states=[[2, 1], [1, 2]], close_cycle=False),
        ],
        "equation_chain": [
            dict(steps=["(x+1)^2", "x^2+2x+1"]),
            dict(steps=["a^2-b^2", "(a-b)(a+b)", r"\text{done}"], labels=["factor", ""]),
        ],
        "geometry_construction": [
            dict(points={"A": [0, 0], "B": [3, 0], "C": [0, 4]},
                 segments=[["A", "B"], ["B", "C"], ["C", "A"]],
                 mark_angles=[["A", "B", "C"]], show_lengths=True),
            dict(points={"P": [-2, -1], "Q": [2, 1]}, segments=[["P", "Q"]]),
        ],
        "vector_field": [
            dict(x_component="-y", y_component="x"),
            dict(x_component="x", y_component="y", density=6),
            dict(x_component="1", y_component="0", normalize=False),
        ],
        # 0 and 180 put the radius along the baseline, where Angle has no unique
        # intersection — the case that broke the first version.
        "unit_circle": [dict(angle_deg=a) for a in (0, 30, 45, 90, 135, 180, 210, 300, 359)],
        "number_line_marks": [
            dict(start=-3, stop=5, marks={"a": -1, "b": 2}, interval=[-1, 2]),
            dict(start=0, stop=1, marks={"x": 0.5}),
        ],
        "matrix_transform": [
            dict(matrix=[[2, 0], [0, 3]], show_eigenvectors=True),
            dict(matrix=[[0, -1], [1, 0]], show_eigenvectors=True),
            dict(matrix=[[1, 1], [0, 1]]),
        ],
        "distribution_plot": [
            dict(distribution="normal", parameters=[0, 1], shade_from=-1, shade_to=1),
            dict(distribution="binomial", parameters=[10, 0.5]),
            dict(distribution="exponential", parameters=[1.5]),
            dict(distribution="poisson", parameters=[3]),
            dict(distribution="uniform", parameters=[0, 1]),
        ],
        "array_cells": [
            dict(values=[1, 3, 5, 7, 9, 11, 13], pointers={"low": 0, "mid": 3, "high": 6}, highlight=[3]),
            dict(values=list(range(20))),
            dict(values=[5, 2, 8], dim=[0, 1]),
        ],
        "free_body_diagram": [
            dict(forces=[{"label": "mg", "magnitude": 9.8, "angle_deg": 270},
                         {"label": "N", "magnitude": 9.8, "angle_deg": 90},
                         {"label": "F", "magnitude": 4, "angle_deg": 0}]),
            dict(shape="dot", forces=[{"label": "T", "magnitude": 5, "angle_deg": 120},
                                      {"label": "W", "magnitude": 5, "angle_deg": 270}]),
            dict(shape="circle", forces=[{"label": f"F_{i}", "magnitude": 3 + i, "angle_deg": 60 * i}
                                         for i in range(6)]),
        ],
        # Every quadrant. The inward normal ends near the centre, which is where
        # the angle arc lives, and that is how the N-on-arc collision was found.
        "circular_motion": [dict(radius=1.6, angle_deg=a) for a in (0, 45, 90, 135, 180, 225, 270, 330)]
        + [dict(radius=2.6, angle_deg=60), dict(radius=0.6, angle_deg=60)],
        "projectile_motion": [
            dict(speed=20, angle_deg=45), dict(speed=8, angle_deg=70),
            dict(speed=30, angle_deg=20), dict(speed=5, angle_deg=85), dict(speed=50, angle_deg=10),
        ],
        "inclined_plane": [dict(angle_deg=a, show_friction=f) for a in (10, 30, 45, 70) for f in (False, True)],
        "energy_bars": [
            dict(entries={"KE": 12.0, "PE": 8.0}), dict(entries={"KE": 0.0, "PE": 20.0}),
            dict(entries={"A": 1, "B": 2, "C": 3, "D": 4}),
        ],
        "wave_form": [
            dict(amplitude=1, wavelength=2, cycles=2), dict(amplitude=0.4, wavelength=0.6, cycles=6),
            dict(amplitude=3, wavelength=5, cycles=1),
        ],
        "iteration_trace": [
            dict(expr="(x-2)**2+1", update_rule="x - 0.2*2*(x-2)", start=-2, steps=10, x_min=-3, x_max=6),
            dict(expr="(x-2)**2+1", update_rule="x - 0.05*2*(x-2)", start=5.5, steps=40, x_min=-3, x_max=6),
            dict(expr="x**2", update_rule="x - 1.1*2*x", start=0.5, steps=12, x_min=-3, x_max=3),
        ],
        "pi_character": [dict()],
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
                    # Minor hits (a curve crossing an axis tick number) are tolerated;
                    # the axis owns its numbering and cannot move it.
                    self.assertEqual(major_collisions([built.group]), [], f"{name} {parameters}")

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

    def test_bus_braking_component_contains_a_2d_bus_and_road(self):
        with tempconfig({"dry_run": True}):
            built = build("bus_braking_road", {"initial_speed_kmh": 72, "stopping_time": 4})
        self.assertIn("bus", built.parts)
        self.assertIn("road", built.parts)
        self.assertTrue(built.beats)

    def test_power_transmission_component_draws_the_full_electricity_setup(self):
        with tempconfig({"dry_run": True}):
            built = build("power_transmission_diagram", {"power_kw": 600, "plant_voltage": 4000, "step_up_ratio": 10, "consumer_voltage": 200})
        self.assertTrue({"power_plant", "step_up_transformer", "high_voltage_line", "step_down_transformer", "consumers"} <= built.parts.keys())

    def test_linear_drag_projectile_marks_the_wall_and_exact_trajectory(self):
        with tempconfig({"dry_run": True}):
            built = build("linear_drag_projectile", {"mass_kg": 0.2, "drag_coefficient": 0.1, "speed": 270, "angle_deg": 60, "wall_time": 2, "e_approx": 2.7})
        self.assertTrue({"axes", "trajectory", "wall", "projectile", "labels"} <= built.parts.keys())

    def test_story_components_provide_real_2d_characters_and_vehicles(self):
        with tempconfig({"dry_run": True}):
            traffic = build("traffic_story", {"vehicle": "car"})
            chase = build("police_bicycle_chase", {"road_turns": 4})
            pi = build("pi_character", {})
        self.assertTrue({"road", "vehicle"} <= traffic.parts.keys())
        self.assertTrue({"zigzag_road", "thief_bicycle", "police_runner"} <= chase.parts.keys())
        self.assertTrue({"pi_glyph", "face", "resting_arm", "scratch_arm_pose", "confusion_marks"} <= pi.parts.keys())

    def test_transport_and_road_safety_objects_are_available(self):
        with tempconfig({"dry_run": True}):
            transport = build("transport_story", {"vehicle": "rocket"})
            safety = build("road_safety_scene", {"show_pedestrian": True})
        self.assertIn("vehicle", transport.parts)
        self.assertTrue({"car", "traffic_light", "pedestrian", "crossing"} <= safety.parts.keys())

    def test_every_choice_of_every_enum_parameter_builds(self):
        """A Literal tested at one value is a Literal that is not tested.

        transport_story was built with vehicle="rocket" and passed, while
        vehicle="airplane" raised NameError — the helper used LEFT and RIGHT
        without importing them. One of four options was covered, and the broken
        one shipped. There are eleven of these enums across the library, so the
        cheapest guard is to walk all of them.
        """
        import typing

        checked = 0
        for name, spec in sorted(COMPONENTS.items()):
            choices = {
                field: list(typing.get_args(info.annotation))
                for field, info in spec.params.model_fields.items()
                if typing.get_origin(info.annotation) is typing.Literal
            }
            if not choices:
                continue
            example = self.CASES.get(name, [{}])[0]
            required = {
                field: example[field]
                for field, info in spec.params.model_fields.items()
                if info.is_required() and field in example
            }
            if any(
                info.is_required() and field not in required
                for field, info in spec.params.model_fields.items()
            ):
                continue  # no example to borrow required parameters from
            for field, options in choices.items():
                for option in options:
                    with self.subTest(component=name, **{field: option}):
                        arguments = {**required, field: option}
                        try:
                            spec.params.model_validate(arguments)
                        except ValidationError:
                            # The component refused the combination. That is it
                            # working: distribution_plot rejects the normal's
                            # [mean, sigma] read as an exponential rate rather
                            # than dividing by zero mid-render. What this test
                            # forbids is crashing on input the model accepted.
                            continue
                        with tempconfig({"dry_run": True}):
                            built = build(name, arguments)
                        self.assertTrue(built.parts, f"{name}({field}={option!r}) built nothing")
                        checked += 1
        self.assertGreater(checked, 20, "enum sweep covered almost nothing")

    def test_unicode_angle_label_is_normalised_before_typesetting(self):
        """Prompts often contain θ, but MathTex receives LaTeX, not Unicode."""
        from proofmotion.tools.typeset import typeset_check

        with tempconfig({"dry_run": True}):
            built = build("circular_motion", {"radius": 1.6, "angle_deg": 60, "label_angle": "θ"})
        expression = built.parts["angle_label"].tex_string
        self.assertEqual(expression, r"\theta")
        self.assertTrue(typeset_check(expression)["valid"])

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
