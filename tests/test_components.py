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
            # The coaxial capacitor cross-section version 1 could not draw:
            # concentric circles, a shaded dielectric annulus, a dashed chord
            # axis, and the chord emphasised between the circles.
            dict(points={"O": [0, 0], "P": [1, 1], "Q": [1, 1.732], "M": [1, -1], "N": [1, -1.732]},
                 circles=[{"center": "O", "radius": 1.414, "label": "a"},
                          {"center": "O", "radius": 2.0, "label": "b"}],
                 shaded=[{"kind": "annulus", "center": "O", "inner": 1.414, "outer": 2.0}],
                 dashed_segments=[[[1, -2.2], [1, 2.2]]],
                 segments=[["P", "Q"], ["M", "N"]]),
            dict(points={"O": [0, 0], "A": [2.5, 0]},
                 circles=[{"center": "O", "radius": 2.5, "dashed": True}],
                 arcs=[{"center": "O", "radius": 1.2, "from_deg": 0, "to_deg": 120, "label": r"\theta"}],
                 vectors=[{"from": "O", "to": "A", "label": "E"}],
                 shaded=[{"kind": "disk", "center": "O", "radius": 0.5, "color_role": "secondary"}]),
            dict(points={"A": [0, 0], "B": [3, 0], "C": [3, 2], "D": [0, 2]},
                 segments=[["A", "B"], ["B", "C"], ["C", "D"], ["D", "A"]],
                 shaded=[{"kind": "polygon", "points": ["A", "B", "C", "D"]}],
                 vectors=[{"from": [1.5, 1], "to": [1.5, 2.8], "label": "F"}]),
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
        "comparison": [
            dict(left_title="SFT", right_title="RLHF",
                 rows=[["labelled demonstrations", "preference pairs"],
                       ["one pass over the data", "reward model + PPO"]]),
            dict(left_title="monolith deployment", right_title="microservice deployment",
                 rows=[["one build artefact for everything", "one artefact per service boundary"],
                       ["a single shared relational database", "each service owns its own store"],
                       ["in-process function calls", "network calls with retries and timeouts"],
                       ["one team ships the whole release", "teams release independently"],
                       ["scaling means a bigger machine", "scaling means more replicas of one part"],
                       ["a bug takes the whole site down", "a bug degrades one capability"],
                       ["simple to trace end to end", "needs distributed tracing to follow"],
                       ["cheap to start, costly to grow", "costly to start, cheaper to grow"]],
                 row_labels=["build", "data", "calls", "release", "scaling", "failure", "debugging", "cost"],
                 highlight=[0, 5]),
            dict(left_title="before", right_title="after",
                 rows=[["manual deploys", ""], ["", "automatic rollback"]]),
        ],
        "hierarchy": [
            dict(edges=[["model", "encoder"]]),
            dict(edges=[["ML", "supervised"], ["ML", "unsupervised"], ["ML", "reinforcement"],
                        ["ML", "self-supervised"], ["ML", "semi-supervised"]]),
            dict(edges=[["compiler", "front end"], ["compiler", "middle end"], ["compiler", "back end"],
                        ["front end", "lexing"], ["front end", "parsing"], ["front end", "type checking"],
                        ["middle end", "SSA"], ["middle end", "inlining"], ["middle end", "loop opts"],
                        ["middle end", "DCE"], ["back end", "instruction selection"],
                        ["back end", "register allocation"], ["back end", "scheduling"],
                        ["back end", "emission"], ["lexing", "tokens"], ["parsing", "AST"],
                        ["SSA", "phi nodes"], ["register allocation", "spilling"]],
                 highlight=["middle end"]),
        ],
        "layers": [
            dict(layers=["hardware", "application"]),
            dict(layers=["physical", "data link", "network", "transport", "session",
                         "presentation", "application"],
                 annotations=["bits on a wire", "frames, MAC", "IP routing", "TCP/UDP",
                              "", "encodings", "HTTP and friends"],
                 highlight=[2, 3]),
        ],
        "grid_map": [
            dict(row_labels=["actual spam"], col_labels=["predicted spam"], cells=[["90"]]),
            dict(row_labels=["s1", "s2", "s3", "s4", "s5", "s6"],
                 col_labels=["a", "b", "c", "d", "e", "f"],
                 cells=[["1", "", "3", "", "5", ""],
                        ["", "2", "", "4", "", "6"],
                        ["7", "8", "", "", "9", "10"],
                        ["", "", "11", "12", "", ""],
                        ["13", "", "", "", "14", ""],
                        ["", "15", "", "16", "", "17"]]),
            dict(row_labels=["low", "medium", "high"],
                 col_labels=["north", "east", "south", "west"],
                 cells=[["3", "1", "4", "1"], ["5", "9", "2", "6"], ["5", "3", "5", "8"]],
                 highlight=[[0, 1], [2, 3]]),
        ],
        "surface_descent": [
            dict(),  # the default bowl
            # A saddle: the descent climbs out along y and leaves the plotted
            # region, which must end the path, not the build.
            dict(expr="x**2 - y**2", steps=4),
            # Steep in y with a hot learning rate: the y iterates overshoot
            # and zigzag across the valley, the classic too-big-eta picture.
            dict(expr="x**2 + 4*y**2", eta=0.2),
        ],
        "surface_plot": [
            # The sine landscape, with a marked point and its drop-line.
            dict(expr="sin(x)*cos(y)", highlight_point=[1.0, 0.5]),
            # A saddle: no marked point, so the motion is the wireframe sweep.
            dict(expr="x**2 - y**2"),
            # A flat plane: zero height span, the projection must not divide
            # by it, and the coincident drop-line must not be drawn.
            dict(expr="2", highlight_point=[0.0, 0.0]),
        ],
        "curve_motion": [
            dict(expr="sin(x) + x/2"),
            # Steep exponential: the tangent's fixed on-screen length is what
            # keeps it inside the frame, which the bounds test then verifies.
            dict(expr="exp(x/2)", at=3.0),
            # The ride starting at the right edge has nowhere to go.
            dict(expr="sin(x) + x/2", at=4.0),
        ],
        "iteration_trace": [
            dict(expr="(x-2)**2+1", update_rule="x - 0.2*2*(x-2)", start=-2, steps=10, x_min=-3, x_max=6),
            dict(expr="(x-2)**2+1", update_rule="x - 0.05*2*(x-2)", start=5.5, steps=40, x_min=-3, x_max=6),
            dict(expr="x**2", update_rule="x - 1.1*2*x", start=0.5, steps=12, x_min=-3, x_max=3),
        ],
        "spyder_math": [
            dict(),
            dict(pose="swing", web=True, anchor_x=2.0, anchor_y=3.2, show_maths=True),
            dict(pose="cast", web=True, facing="left", at_x=1.5, anchor_x=-3.0, anchor_y=3.5, show_maths=True),
            dict(pose="run_contact", facing="left", at_x=-2.0, show_maths=True),
            dict(pose="dab", at_x=3.0),
            dict(pose="flail", web=True, anchor_x=-1.0, anchor_y=4.0, at_x=-3.5, show_maths=True),
            dict(pose="victory"),
        ],
        "proofmotion": [
            dict(),
            dict(form="swing_line"),
            dict(form="ramp", mood="agitated", seed=3),
            dict(form="spiral", at_x=1.0),
            dict(form="arches", span=7.5, mood="agitated"),
            dict(form="steps", height=3.0, seed=11),
            dict(form="orb", mood="agitated", at_x=-2.0, seed=99),
            dict(form="swing_line", span=8.0, height=4.0, at_x=0.0),
        ],
        "math_scene": [
            dict(),
            dict(beat="run_the_ramp", show_maths=True),
            dict(beat="climb_the_steps", show_maths=True, seed=4),
            dict(beat="ride_the_spiral"),
            dict(beat="standoff"),
            dict(beat="swing_across", hero_x=-3.5, show_maths=True),
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
        self.assertTrue({"road", "vehicle"} <= traffic.parts.keys())
        self.assertTrue({"zigzag_road", "thief_bicycle", "police_runner"} <= chase.parts.keys())

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


class CharacterTests(unittest.TestCase):
    """The rig, the shape-shifter and the scene keep their computed promises."""

    def test_an_unknown_pose_is_refused_with_the_choices(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("spyder_math", {"pose": "moonwalk"})
        message = str(caught.exception)
        for choice in ("stand", "crouch", "swing", "cast", "run_contact", "victory", "defeated", "dab", "flail"):
            self.assertIn(choice, message, f"the refusal must list {choice!r}")

    def test_an_unknown_form_is_refused_with_the_choices(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("proofmotion", {"form": "cube"})
        message = str(caught.exception)
        for choice in ("orb", "swing_line", "ramp", "spiral", "arches", "steps"):
            self.assertIn(choice, message, f"the refusal must list {choice!r}")

    def test_orb_chords_are_deterministic_in_the_seed(self):
        def endpoints(seed):
            with tempconfig({"dry_run": True}):
                built = build("proofmotion", {"form": "orb", "seed": seed})
            return [
                (tuple(round(float(v), 6) for v in line.get_start()),
                 tuple(round(float(v), 6) for v in line.get_end()))
                for line in built.parts["chords"]
            ]

        self.assertEqual(endpoints(7), endpoints(7), "one seed must rebuild the same chords")
        self.assertNotEqual(endpoints(7), endpoints(8), "a different seed must grow a different orb")

    def test_the_web_is_a_taut_pendulum_line_from_the_anchor(self):
        import numpy as np
        from manim import Line

        with tempconfig({"dry_run": True}):
            built = build("spyder_math", {"pose": "swing", "web": True})
        web = next(m for m in built.parts["web"].family_members_with_points() if isinstance(m, Line))
        anchor = built.parts["anchor"].get_center()
        self.assertLess(float(np.linalg.norm(web.get_start() - anchor)), 1e-6)
        # The pendulum constraint: the line's length is exactly the wrist's distance.
        span = float(np.linalg.norm(web.get_end() - web.get_start()))
        self.assertAlmostEqual(float(web.get_length()), span, places=6)
        # And the far end holds the figure's wrist, so it must lie on the figure.
        left, right, bottom, top = bounds(built.parts["figure"])
        x, y = float(web.get_end()[0]), float(web.get_end()[1])
        self.assertTrue(left - 1e-6 <= x <= right + 1e-6)
        self.assertTrue(bottom - 1e-6 <= y <= top + 1e-6)

    def test_the_scene_resolves_every_beat_with_hero_and_world(self):
        for beat in ("swing_across", "run_the_ramp", "climb_the_steps", "ride_the_spiral", "standoff"):
            with self.subTest(beat=beat), tempconfig({"dry_run": True}):
                built = build("math_scene", {"beat": beat})
                self.assertIn("hero", built.parts)
                self.assertIn("world", built.parts)
                for reveal in built.beats:
                    for part in reveal:
                        self.assertIn(part, built.parts, f"{beat}: beat names missing part {part!r}")
                self.assertTrue(built.motions, f"{beat} carries no motion")

    def test_traversals_keep_the_hero_on_the_surface(self):
        """The trajectory starts under the hero's feet and ends on the world's top."""
        for beat in ("run_the_ramp", "climb_the_steps"):
            with self.subTest(beat=beat), tempconfig({"dry_run": True}):
                built = build("math_scene", {"beat": beat, "show_maths": True})
                trajectory = built.parts["trajectory"]
                hero_lowest = bounds(built.parts["hero"])[2]
                start_y = float(trajectory.get_start()[1])
                self.assertLess(abs(hero_lowest - start_y), 0.08, f"{beat}: the hero floats at the start")
                world_top = bounds(built.parts["world"])[3]
                end_y = float(trajectory.get_end()[1])
                self.assertLess(abs(end_y - world_top), 0.08, f"{beat}: the traversal misses the summit")

    def test_planted_poses_stand_on_the_ground_line(self):
        for pose in ("stand", "crouch", "run_contact", "cast", "brace", "victory", "defeated", "dab"):
            with self.subTest(pose=pose), tempconfig({"dry_run": True}):
                built = build("spyder_math", {"pose": pose, "show_maths": False})
                ground_y = float(built.parts["ground"].get_start()[1])
                lowest = bounds(built.parts["figure"])[2]
                self.assertLess(abs(lowest - ground_y), 0.05, f"{pose} floats off the ground")


class SurfaceDescentTests(unittest.TestCase):
    """surface_descent computes its descent and refuses nonsense plainly."""

    def test_a_garbage_expression_is_refused_plainly(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("surface_descent", {"expr": "x*** + squiggle("})
        message = str(caught.exception)
        self.assertIn("could not parse", message)
        self.assertNotIn("Traceback", message)

    def test_an_unknown_symbol_is_refused_naming_it(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("surface_descent", {"expr": "x**2 + w**2"})
        self.assertIn("w", str(caught.exception))
        self.assertIn("only x and y", str(caught.exception))

    def test_a_start_outside_the_range_is_refused(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError):
            build("surface_descent", {"start": [9.0, 0.0]})

    def test_the_default_bowl_iterates_are_the_hand_computed_contraction(self):
        """For x^2 + 2y^2 with eta 0.1 the map is exactly (0.8x, 0.6y)."""
        with tempconfig({"dry_run": True}):
            built = build("surface_descent", {})
        for k in range(1, 8):
            pair = f"({3 * 0.8**k:.2f}, {2 * 0.6**k:.2f})"
            self.assertIn(pair, built.notes, f"step {k} missing from notes: {built.notes}")
        self.assertIn("f falls 17", built.notes)

    def test_a_path_that_leaves_the_region_still_builds_and_says_so(self):
        """On the saddle the descent climbs out along y; the path must stop
        at the plotted edge and the notes must report the early exit."""
        with tempconfig({"dry_run": True}):
            built = build("surface_descent", {"expr": "x**2 - y**2", "steps": 8})
        self.assertIn("leaves the plotted region", built.notes)
        self.assertTrue(built.parts)

    def test_same_parameters_build_identical_notes(self):
        parameters = {"expr": "x**2 + 2*y**2", "start": [3.0, 2.0], "eta": 0.1, "steps": 7}
        with tempconfig({"dry_run": True}):
            first = build("surface_descent", parameters).notes
            second = build("surface_descent", parameters).notes
        self.assertEqual(first, second)


class SurfacePlotAndCurveMotionTests(unittest.TestCase):
    """The general surface and the curve ride refuse nonsense and keep the drawn slope honest."""

    def test_garbage_expressions_are_refused_plainly(self):
        from proofmotion.runtime.registry import ToolError

        for name in ("surface_plot", "curve_motion"):
            with self.subTest(component=name):
                with self.assertRaises(ToolError) as caught:
                    build(name, {"expr": "x*** + squiggle("})
                message = str(caught.exception)
                self.assertIn("could not parse", message)
                self.assertNotIn("Traceback", message)

    def test_unknown_symbols_are_refused_naming_them(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("surface_plot", {"expr": "x**2 + q*y"})
        self.assertIn("q", str(caught.exception))
        self.assertIn("only x and y", str(caught.exception))
        with self.assertRaises(ToolError) as caught:
            build("curve_motion", {"expr": "sin(x) + t"})
        self.assertIn("t", str(caught.exception))
        self.assertIn("only x", str(caught.exception))

    def test_a_start_outside_the_range_is_refused(self):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("curve_motion", {"expr": "x**2", "at": 9.0})
        self.assertIn("outside", str(caught.exception))
        with self.assertRaises(ToolError):
            build("surface_plot", {"highlight_point": [9.0, 0.0]})

    def test_the_tangent_slope_is_the_sympy_derivative_at_the_start(self):
        """The drawn tangent's endpoints, mapped back through the axes, must
        give exactly f'(at) — for sin(x) + x/2 at 1.25 that is cos(1.25) + 1/2."""
        import math

        with tempconfig({"dry_run": True}):
            built = build("curve_motion", {"expr": "sin(x) + x/2", "at": 1.25})
        axes, tangent = built.parts["axes"], built.parts["tangent"]
        ax, ay = axes.point_to_coords(tangent.get_start())[:2]
        bx, by = axes.point_to_coords(tangent.get_end())[:2]
        slope = (by - ay) / (bx - ax)
        self.assertAlmostEqual(slope, math.cos(1.25) + 0.5, delta=1e-6)

    def test_a_ride_from_the_right_edge_has_no_motion_and_says_so(self):
        with tempconfig({"dry_run": True}):
            built = build("curve_motion", {"expr": "sin(x) + x/2", "at": 4.0})
        self.assertEqual(built.motions, [])
        self.assertIn("right edge", built.notes)

    def test_a_marked_surface_point_pulses_and_a_bare_surface_sweeps(self):
        with tempconfig({"dry_run": True}):
            marked = build("surface_plot", {"expr": "sin(x)*cos(y)", "highlight_point": [1.0, 0.5]})
            bare = build("surface_plot", {"expr": "sin(x)*cos(y)"})
        self.assertIn("point", marked.parts)
        self.assertIn("drop", marked.parts)
        self.assertIn("pulses", marked.notes)
        self.assertNotIn("point", bare.parts)
        self.assertIn("sweeps", bare.notes)
        self.assertTrue(marked.motions and bare.motions)


class GeometryPrimitiveTests(unittest.TestCase):
    """geometry_construction's circles, arcs and shaded regions refuse nonsense plainly."""

    def refuse(self, parameters, keyword):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build("geometry_construction", parameters)
        self.assertIn(keyword, str(caught.exception))

    def test_an_unknown_circle_center_is_refused_naming_the_point(self):
        self.refuse(
            dict(points={"A": [0, 0], "B": [1, 0]}, circles=[{"center": "Z", "radius": 1.0}]),
            "'Z'",
        )

    def test_an_annulus_whose_inner_radius_is_not_below_its_outer_is_refused(self):
        self.refuse(
            dict(points={"O": [0, 0]},
                 shaded=[{"kind": "annulus", "center": "O", "inner": 2.0, "outer": 1.4}]),
            "inner radius must be smaller",
        )

    def test_a_two_point_polygon_is_refused(self):
        self.refuse(
            dict(shaded=[{"kind": "polygon", "points": [[0, 0], [1, 1]]}]),
            "at least three",
        )

    def test_old_style_points_and_segments_still_build(self):
        with tempconfig({"dry_run": True}):
            built = build(
                "geometry_construction",
                dict(points={"A": [0, 0], "B": [3, 0], "C": [0, 4]},
                     segments=[["A", "B"], ["B", "C"], ["C", "A"]]),
            )
        for part in ("point_A", "segment_0", "label_A"):
            self.assertIn(part, built.parts)
        for beat in built.beats:
            for name in beat:
                self.assertIn(name, built.parts)


class ShapeValidatorTests(unittest.TestCase):
    """The shape components refuse malformed structure with a plain sentence."""

    def refuse(self, name, parameters, keyword):
        from proofmotion.runtime.registry import ToolError

        with self.assertRaises(ToolError) as caught:
            build(name, parameters)
        self.assertIn(keyword, str(caught.exception))

    def test_comparison_rejects_a_row_that_is_not_a_pair(self):
        self.refuse(
            "comparison",
            dict(left_title="a", right_title="b", rows=[["one", "two", "three"]]),
            "exactly two cells",
        )

    def test_hierarchy_rejects_two_roots(self):
        self.refuse("hierarchy", dict(edges=[["a", "b"], ["c", "d"]]), "exactly one root")

    def test_hierarchy_rejects_a_cycle(self):
        self.refuse(
            "hierarchy",
            dict(edges=[["root", "a"], ["b", "c"], ["c", "b"]]),
            "cycle",
        )

    def test_hierarchy_rejects_a_tree_five_levels_deep(self):
        self.refuse(
            "hierarchy",
            dict(edges=[["a", "b"], ["b", "c"], ["c", "d"], ["d", "e"]]),
            "levels deep",
        )

    def test_grid_map_rejects_ragged_cells(self):
        self.refuse(
            "grid_map",
            dict(row_labels=["r1", "r2"], col_labels=["c1", "c2"],
                 cells=[["1", "2"], ["3", "4", "5"]]),
            "column labels",
        )

    def test_layers_rejects_mismatched_annotations(self):
        self.refuse(
            "layers",
            dict(layers=["hardware", "kernel", "application"], annotations=["only one"]),
            "annotations",
        )


if __name__ == "__main__":
    unittest.main()
