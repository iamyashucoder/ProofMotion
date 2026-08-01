"""The service layer: locks per project, one bounded pool, honest snapshots.

No API key required, and no Manim process is ever spawned — the turn and the
renderer are replaced with recording fakes; what is under test is the wiring
around them: what gets applied, saved, remembered, and reported.
"""

from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from proofmotion.studio import Project, Slide
from proofmotion.studio.jobs import RenderPool
from proofmotion.studio.operations import Edit, Operation
from proofmotion.studio.service import StudioService
from proofmotion.studio.store import ProjectStore
from proofmotion.studio.turns import TurnResult

CLEAN_REPORT = {
    "rendered": 1, "reused": 0, "failed": 0, "problems": [],
    "video": "video.mp4", "seconds": 6.0, "errors": {}, "partial": False, "units": [],
}


def service(root: Path) -> StudioService:
    return StudioService(ProjectStore(root), client=None, pool=RenderPool(max_workers=2))


def seeded(root: Path) -> tuple[StudioService, str]:
    s = service(root)
    project = Project.create(s.store.new_id(), "a question")
    project.slides = [Slide(id="s1", title="One")]
    s.store.save(project)
    return s, project.project_id


class TestRunTurn(unittest.TestCase):
    def test_a_turn_applies_saves_rebuilds_and_remembers(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, pid = seeded(Path(tmp))
            builds = []

            def fake_build(project, directory, *, only=None, run=None):
                builds.append(only)
                return dict(CLEAN_REPORT)

            turn = TurnResult(Edit(
                operations=[Operation(kind="edit", slide_id="s1", title="Better")],
                reply="made it better",
            ))
            with (
                patch("proofmotion.studio.turns.run_turn", return_value=turn),
                patch("proofmotion.studio.render.build", side_effect=fake_build),
            ):
                out = s.run_turn(pid, "improve the title")

            self.assertEqual(out["reply"], "made it better")
            self.assertEqual(builds, [["s1"]])
            back = s.store.load(pid)
            self.assertEqual(back.slides[0].title, "Better")
            thread = s.store.transcript(pid)
            self.assertEqual([t["who"] for t in thread], ["you", "bot"])
            self.assertEqual(thread[1]["text"], "made it better")

    def test_a_refusal_applies_nothing_and_renders_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, pid = seeded(Path(tmp))
            turn = TurnResult(Edit(), refusal="ask it in the main box")
            with (
                patch("proofmotion.studio.turns.run_turn", return_value=turn),
                patch("proofmotion.studio.render.build") as build,
            ):
                out = s.run_turn(pid, "how do we find pi?", remake_slide="s1")
            self.assertEqual(out["reply"], "ask it in the main box")
            build.assert_not_called()
            self.assertEqual(s.store.load(pid).slides[0].title, "One")

    def test_the_first_message_becomes_the_question(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = service(Path(tmp))
            turn = TurnResult(Edit(operations=[Operation(kind="add", title="T")], reply="ok"))
            with (
                patch("proofmotion.studio.turns.run_turn", return_value=turn),
                patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
            ):
                out = s.create_project("why is the sky blue")
            back = s.store.load(out["project_id"])
            self.assertEqual(back.question, "why is the sky blue")
            self.assertEqual(len(back.slides), 1)


class TestOperations(unittest.TestCase):
    def test_a_lock_invalidates_no_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, pid = seeded(Path(tmp))
            builds = []

            def fake_build(project, directory, *, only=None, run=None):
                builds.append(only)
                return dict(CLEAN_REPORT)

            with patch("proofmotion.studio.render.build", side_effect=fake_build):
                s.apply_operations(pid, [Operation(kind="lock", slide_id="s1", locked=True)])
            self.assertEqual(builds, [[]])
            self.assertTrue(s.store.load(pid).slides[0].locked)

    def test_a_refused_operation_reports_and_saves_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, pid = seeded(Path(tmp))
            s.apply_operations(pid, [Operation(kind="lock", slide_id="s1", locked=True)])
            with patch("proofmotion.studio.render.build") as build:
                out = s.apply_operations(
                    pid, [Operation(kind="edit", slide_id="s1", title="sneaky")]
                )
            self.assertIn("error", out)
            self.assertEqual(s.store.load(pid).slides[0].title, "One")

    def test_render_failures_land_in_the_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, pid = seeded(Path(tmp))
            broken = {
                **CLEAN_REPORT, "rendered": 0, "failed": 1, "video": "video.mp4",
                "partial": True, "errors": {"s1": "manim fell over"},
                "problems": [{"slides": ["s1"], "error": "manim fell over"}],
            }
            with patch("proofmotion.studio.render.build", return_value=broken):
                out = s.rerender(pid, "s1")
            self.assertEqual(out["errors"], {"s1": "manim fell over"})
            self.assertTrue(out["partial"])
            self.assertIn("manim fell over", out["status"])


class TestVisualizerPass(unittest.TestCase):
    """A turn that leaves the deck mostly words gets one illustration pass."""

    PLOT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0}

    def wordy_turn(self):
        return TurnResult(Edit(operations=[
            Operation(kind="add", title=f"Step {i}", caption="f(x) = x^2") for i in range(4)
        ], reply="derived"))

    def test_a_wordy_deck_is_sent_to_the_visualizer(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = service(Path(tmp))
            project = Project.create(s.store.new_id(), "q")
            s.store.save(project)
            drawn = Edit(operations=[Operation(
                kind="edit", slide_id="s2", component="function_plot",
                parameters=dict(self.PLOT),
            )])
            with (
                patch("proofmotion.studio.turns.run_turn", return_value=self.wordy_turn()),
                patch("proofmotion.agents.visualizer.illustrate", return_value=drawn) as doctor,
                patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
            ):
                out = s.run_turn(project.project_id, "explain it")
            doctor.assert_called_once()
            back = s.store.load(project.project_id)
            self.assertEqual(back.slide("s2").component, "function_plot")
            self.assertIn("Illustrated 1 slide(s).", out["reply"])

    def test_a_deck_that_already_draws_is_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = service(Path(tmp))
            project = Project.create(s.store.new_id(), "q")
            s.store.save(project)
            drawing = TurnResult(Edit(operations=[
                Operation(kind="add", title=f"Fig {i}", component="function_plot",
                          parameters=dict(self.PLOT))
                for i in range(4)
            ], reply="drawn already"))
            with (
                patch("proofmotion.studio.turns.run_turn", return_value=drawing),
                patch("proofmotion.agents.visualizer.illustrate") as doctor,
                patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
            ):
                s.run_turn(project.project_id, "explain it")
            doctor.assert_not_called()

    def test_a_failed_pass_never_takes_the_deck_down(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = service(Path(tmp))
            project = Project.create(s.store.new_id(), "q")
            s.store.save(project)
            with (
                patch("proofmotion.studio.turns.run_turn", return_value=self.wordy_turn()),
                patch("proofmotion.agents.visualizer.illustrate", side_effect=RuntimeError("api down")),
                patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
            ):
                out = s.run_turn(project.project_id, "explain it")
            self.assertEqual(len(out["slides"]), 4, "the deck ships either way")


class TestConcurrency(unittest.TestCase):
    def test_two_projects_run_turns_side_by_side(self):
        """Per-project locks: one studio-wide mutex was the scalability ceiling."""
        with tempfile.TemporaryDirectory() as tmp:
            s, first = seeded(Path(tmp))
            project = Project.create(s.store.new_id(), "another")
            project.slides = [Slide(id="s1")]
            s.store.save(project)
            second = project.project_id

            def slow_turn(client, proj, message, *, remake_slide="", images=None):
                time.sleep(0.25)
                return TurnResult(Edit(reply="done"))

            with (
                patch("proofmotion.studio.turns.run_turn", side_effect=slow_turn),
                patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
            ):
                started = time.monotonic()
                threads = [
                    threading.Thread(target=s.run_turn, args=(pid, "go"))
                    for pid in (first, second)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                elapsed = time.monotonic() - started
            self.assertLess(elapsed, 0.45, "different projects must not queue on each other")

    def test_turns_on_one_project_take_turns(self):
        with tempfile.TemporaryDirectory() as tmp:
            s, pid = seeded(Path(tmp))

            def slow_turn(client, proj, message, *, remake_slide="", images=None):
                time.sleep(0.2)
                return TurnResult(Edit(reply="done"))

            with (
                patch("proofmotion.studio.turns.run_turn", side_effect=slow_turn),
                patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
            ):
                started = time.monotonic()
                threads = [
                    threading.Thread(target=s.run_turn, args=(pid, "go")) for _ in range(2)
                ]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
                elapsed = time.monotonic() - started
            self.assertGreaterEqual(elapsed, 0.4, "one project's turns must serialise")


class TestRenderPool(unittest.TestCase):
    def test_the_pool_bounds_concurrent_poster_renders(self):
        """Eight thumbnails at once must not mean eight Manim processes."""
        in_flight, peak = [0], [0]
        gauge = threading.Lock()

        def fake_poster(slide, directory, *, style="dark", quality="l"):
            with gauge:
                in_flight[0] += 1
                peak[0] = max(peak[0], in_flight[0])
            time.sleep(0.05)
            with gauge:
                in_flight[0] -= 1
            return None

        pool = RenderPool(max_workers=2)
        with tempfile.TemporaryDirectory() as tmp, patch(
            "proofmotion.studio.render.poster", side_effect=fake_poster
        ):
            threads = [
                threading.Thread(target=pool.poster, args=(Slide(id=f"s{i}"), Path(tmp)))
                for i in range(8)
            ]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertLessEqual(peak[0], 2)


if __name__ == "__main__":
    unittest.main()
