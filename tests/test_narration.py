"""Narration rides the document end to end, and never touches the cache.

The director writes narration for every scene; it used to be dropped on the
way to the document — generated on every run, reaching nothing. These tests
hold the whole route open (storyboard → assignment → operation → slide →
disk) and hold the one rule that makes it cheap: words change no pixels, so
editing them must never cost a render.

No API key required.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proofmotion.studio import Project, Slide, digest_of
from proofmotion.studio.operations import Operation, apply

PLOT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0}


class TestNarrationRoute(unittest.TestCase):
    def test_the_storyboard_narration_reaches_the_assignment(self):
        from proofmotion.compose.derive import plan_from_storyboard

        storyboard = {
            "scenes": [{
                "title": "The parabola",
                "visual_objects": [{"name": "function_plot", "parameters": PLOT}],
                "equations": ["y = x^2"],
                "narration": "Here is the curve we will study.",
                "duration_seconds": 6,
            }]
        }
        plan = plan_from_storyboard(storyboard)
        self.assertIsNotNone(plan)
        self.assertEqual(plan.assignments[0].narration, "Here is the curve we will study.")

    def test_an_add_operation_carries_narration_onto_the_slide(self):
        project = Project.create("test", "q")
        apply(project, Operation(
            kind="add", title="One", component="function_plot", parameters=PLOT,
            narration="The curve rises quadratically.",
        ))
        self.assertEqual(project.slides[0].narration, "The curve rises quadratically.")

    def test_an_edit_changes_only_the_narration(self):
        project = Project.create("test", "q")
        project.slides = [Slide(id="s1", title="One", narration="old words")]
        apply(project, Operation(kind="edit", slide_id="s1", narration="new words"))
        self.assertEqual(project.slides[0].narration, "new words")
        self.assertEqual(project.slides[0].title, "One")
        apply(project, Operation(kind="edit", slide_id="s1", title="Two"))
        self.assertEqual(project.slides[0].narration, "new words", "None must mean keep")

    def test_narration_survives_the_disk(self):
        project = Project.create("test", "q")
        project.slides = [Slide(id="s1", narration="say this", title="t")]
        with tempfile.TemporaryDirectory() as tmp:
            project.save(tmp)
            back = Project.load(Path(tmp))
        self.assertEqual(back.slides[0].narration, "say this")

    def test_narration_never_moves_the_digest(self):
        """The caching guard: words change no pixels."""
        silent = Slide(id="s1", component="function_plot", parameters=PLOT)
        spoken = Slide(id="s1", component="function_plot", parameters=PLOT,
                       narration="a whole paragraph of speech")
        self.assertEqual(digest_of([silent]), digest_of([spoken]))


class TestDuplicateKeepsThePlacement(unittest.TestCase):
    def test_an_add_operation_can_carry_overrides(self):
        """A duplicate without the hand placement is not a duplicate."""
        nudged = {"shift": {"caption": {"dx": 0.4, "dy": -0.2}}}
        project = Project.create("test", "q")
        project.slides = [Slide(id="s1", title="One", component="function_plot",
                                parameters=PLOT, overrides=nudged)]
        source = project.slides[0]
        apply(project, Operation(
            kind="add", after="s1", title=source.title, component=source.component,
            parameters=dict(source.parameters), overrides=dict(source.overrides),
        ))
        copy = project.slides[1]
        self.assertNotEqual(copy.id, source.id)
        self.assertEqual(copy.overrides, nudged)
        # And the copy renders as its own unit: same content, same digest.
        self.assertEqual(digest_of([source]), digest_of([copy]))


class TestSpeech(unittest.TestCase):
    def test_the_speech_key_is_the_content(self):
        from proofmotion.studio.narrate import speech_digest

        base = speech_digest("hello there", "en_US-lessac-medium")
        self.assertEqual(base, speech_digest("hello there", "en_US-lessac-medium"))
        self.assertNotEqual(base, speech_digest("hello here", "en_US-lessac-medium"))
        self.assertNotEqual(base, speech_digest("hello there", "en_GB-alba-medium"))

    def test_audio_lives_under_the_project_keyed_by_content(self):
        from proofmotion.studio.narrate import audio_path, speech_digest

        path = audio_path("say this", "voice", Path("/proj"))
        self.assertEqual(path, Path("/proj/audio") / f"{speech_digest('say this', 'voice')}.wav")

    def test_a_missing_voice_names_the_exact_remedy(self):
        """No mock, no silent skip: the error is the installation instructions."""
        import os
        from unittest.mock import patch as patch_env

        from proofmotion.runtime.registry import ToolError
        from proofmotion.studio import narrate

        with tempfile.TemporaryDirectory() as tmp:
            narrate._engine.cache_clear()
            with patch_env.dict(os.environ, {"PROOFMOTION_VOICE_DIR": tmp}):
                with self.assertRaises(ToolError) as caught:
                    narrate.synthesize("hello", "en_US-lessac-medium", Path(tmp))
            narrate._engine.cache_clear()
        message = str(caught.exception)
        self.assertTrue(
            "pip install 'proofmotion[speech]'" in message
            or "download_voices" in message,
            message,
        )

    def test_empty_narration_is_refused_not_silence(self):
        from proofmotion.runtime.registry import ToolError
        from proofmotion.studio.narrate import synthesize

        with self.assertRaises(ToolError):
            synthesize("   ", "any", Path("/nowhere"))

    def test_speaking_a_real_phrase(self):
        from proofmotion.studio import narrate

        try:
            import piper  # noqa: F401
        except ImportError:
            self.skipTest("piper-tts not installed")
        if not (narrate.voice_dir() / f"{narrate.DEFAULT_VOICE}.onnx").is_file():
            self.skipTest("default voice not downloaded")

        with tempfile.TemporaryDirectory() as tmp:
            wav = narrate.synthesize("The tangent line touches the curve.",
                                     narrate.DEFAULT_VOICE, Path(tmp))
            self.assertGreater(narrate.seconds_of(wav), 0.5)


class TestSchedule(unittest.TestCase):
    """Where the words land in the film: real durations, honest overflows."""

    def placements(self, units, project, tmp, durations, lengths):
        """Run audio_schedule with measured durations and spoken lengths faked."""
        from unittest.mock import patch

        from proofmotion.studio import narrate

        def fake_clip_seconds(clip):
            return durations[clip.name]

        def fake_synthesize(text, voice, directory):
            return Path(tmp) / f"{narrate.speech_digest(text, voice)}.wav"

        def fake_seconds_of(wav):
            return lengths[wav.name]

        with (
            patch("proofmotion.studio.narrate.clip_seconds", side_effect=fake_clip_seconds),
            patch("proofmotion.studio.narrate.synthesize", side_effect=fake_synthesize),
            patch("proofmotion.studio.narrate.seconds_of", side_effect=fake_seconds_of),
        ):
            return narrate.audio_schedule(units, project, Path(tmp))

    def test_offsets_accumulate_and_split_proportionally(self):
        from proofmotion.studio.narrate import speech_digest
        from proofmotion.studio.render import Unit

        project = Project.create("test", "q")
        first = Slide(id="s1", narration="first words", seconds=6.0)
        second = Slide(id="s2", narration="second words", seconds=4.0)
        third = Slide(id="s3", narration="third words", seconds=2.0)
        # One unit of one slide (8s real), one unit of two slides (6s real,
        # declared 4+2 → split 4 and 2).
        units = [
            Unit(slides=[first], digest="aaaa", clip=Path("/c/aaaa.mp4")),
            Unit(slides=[second, third], digest="bbbb", clip=Path("/c/bbbb.mp4")),
        ]
        durations = {"aaaa.mp4": 8.0, "bbbb.mp4": 6.0}
        lengths = {
            f"{speech_digest('first words', 'en_US-lessac-medium')}.wav": 5.0,
            f"{speech_digest('second words', 'en_US-lessac-medium')}.wav": 3.0,
            f"{speech_digest('third words', 'en_US-lessac-medium')}.wav": 1.5,
        }
        with tempfile.TemporaryDirectory() as tmp:
            placements, problems = self.placements(units, project, tmp, durations, lengths)
        self.assertEqual([ms for _, ms in placements], [0, 8000, 12000])
        self.assertEqual(problems, [])

    def test_overlong_speech_is_placed_and_reported_never_trimmed(self):
        from proofmotion.studio.narrate import speech_digest
        from proofmotion.studio.render import Unit

        project = Project.create("test", "q")
        slide = Slide(id="s1", narration="a very long speech", seconds=6.0)
        units = [Unit(slides=[slide], digest="aaaa", clip=Path("/c/aaaa.mp4"))]
        lengths = {f"{speech_digest('a very long speech', 'en_US-lessac-medium')}.wav": 9.2}
        with tempfile.TemporaryDirectory() as tmp:
            placements, problems = self.placements(
                units, project, tmp, {"aaaa.mp4": 6.0}, lengths
            )
        self.assertEqual(len(placements), 1, "the audio is still placed")
        self.assertEqual(len(problems), 1)
        self.assertIn("s1", problems[0])
        self.assertIn("lengthen the slide or shorten the note", problems[0])

    def test_a_failed_unit_is_absent_from_the_timeline(self):
        from unittest.mock import patch

        from proofmotion.studio import narrate
        from proofmotion.studio.render import Unit

        project = Project.create("test", "q")
        spoken = Slide(id="s2", narration="after the gap", seconds=6.0)
        units = [
            Unit(slides=[Slide(id="s1", narration="never rendered")], digest="dead", error="boom"),
            Unit(slides=[spoken], digest="bbbb", clip=Path("/c/bbbb.mp4")),
        ]
        with (
            patch("proofmotion.studio.narrate.clip_seconds", return_value=6.0),
            patch("proofmotion.studio.narrate.synthesize", return_value=Path("/a.wav")),
            patch("proofmotion.studio.narrate.seconds_of", return_value=2.0),
        ):
            placements, _ = narrate.audio_schedule(units, project, Path("/nowhere"))
        # The surviving clip is the whole film, so its speech starts at zero.
        self.assertEqual([ms for _, ms in placements], [0])


class TestMuxCommand(unittest.TestCase):
    def test_the_command_copies_video_and_mixes_delayed_speech(self):
        from proofmotion.studio.narrate import mux_command

        command = mux_command(
            Path("/p/video.mp4"),
            [(Path("/p/audio/a.wav"), 0), (Path("/p/audio/b.wav"), 8000)],
            Path("/p/.video-spoken.mp4"),
            41.5,
        )
        joined = " ".join(command)
        self.assertIn("-c:v copy", joined)
        self.assertIn("adelay=8000|8000", joined)
        self.assertIn("amix=inputs=2:normalize=0", joined)
        self.assertIn("-shortest", joined)
        self.assertEqual(command.count("-i"), 3)

    def test_the_pad_is_bounded_by_the_films_length(self):
        """Bare `apad` never ends, and `-shortest` does not stop a filtergraph.

        Together they hung a thirteen-slide render until ffmpeg was killed.
        """
        from proofmotion.studio.narrate import mux_command

        command = mux_command(
            Path("/p/video.mp4"), [(Path("/p/audio/a.wav"), 0)],
            Path("/p/out.mp4"), 41.5,
        )
        joined = " ".join(command)
        self.assertIn("apad=whole_dur=41.500", joined)
        self.assertNotIn("apad[aout]", joined)

    def test_fit_narration_lengthens_exactly_the_short_slides(self):
        from unittest.mock import patch

        from proofmotion.studio import narrate

        project = Project.create("test", "q")
        short = Slide(id="s1", narration="long speech", seconds=3.0)
        fine = Slide(id="s2", narration="short speech", seconds=10.0)
        silent = Slide(id="s3", seconds=2.0)
        project.slides = [short, fine, silent]

        def fake_synthesize(text, voice, directory):
            return Path(f"/{text.split()[0]}.wav")

        lengths = {"/long.wav": 7.4, "/short.wav": 2.0}
        with (
            patch("proofmotion.studio.narrate.synthesize", side_effect=fake_synthesize),
            patch("proofmotion.studio.narrate.seconds_of",
                  side_effect=lambda wav: lengths[str(wav)]),
        ):
            fitted = narrate.fit(project, Path("/nowhere"))
        self.assertEqual(fitted, ["s1"])
        self.assertEqual(short.seconds, 9.0)  # ceil(7.4 + 0.8)
        self.assertEqual(fine.seconds, 10.0)
        self.assertEqual(silent.seconds, 2.0)


if __name__ == "__main__":
    unittest.main()
