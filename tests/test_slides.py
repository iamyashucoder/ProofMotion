"""The deck as slides: manim-slides assembly over the studio's own clips.

The fragments come from the cached clips — that economics is kept — while
stepping, loops, speaker notes and the exports belong to manim-slides.

Needs ffmpeg; no API key, no Manim render (clips are synthesized).
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import render, slides
from proofmotion.studio.document import Project, Slide

PLOT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0}
TANGENT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0, "at": 2.0}


def deck() -> Project:
    project = Project.create("test", "q")
    project.slides = [
        Slide(id="s1", title="One", component="function_plot", parameters=dict(PLOT),
              narration="the first thought"),
        Slide(id="s2", title="Two", component="tangent_secant", parameters=dict(TANGENT),
              narration="", loop=True),
    ]
    return project


def fake_clips(project: Project, directory: Path) -> None:
    (directory / "clips").mkdir(parents=True, exist_ok=True)
    for unit in render.units_of(project):
        clip = directory / "clips" / f"{unit.digest}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "color=c=black:s=64x36:d=1", str(clip)],
            check=True, timeout=60,
        )


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class TestPresentation(unittest.TestCase):
    def test_one_presentation_slide_per_unit_with_notes_and_loops(self):
        project = deck()
        with tempfile.TemporaryDirectory() as tmp:
            fake_clips(project, Path(tmp))
            config, path = slides.presentation(project, Path(tmp))
        self.assertEqual(len(config.slides), 2)
        self.assertIn("One: the first thought", config.slides[0].notes)
        self.assertFalse(config.slides[0].loop)
        self.assertTrue(config.slides[1].loop, "the marked slide loops")
        self.assertTrue(str(path).endswith("presentation.json"))

    def test_every_fragment_carries_an_audio_stream(self):
        """Players expect audio; a silent slide gets a silent stream, not none."""
        project = deck()
        with tempfile.TemporaryDirectory() as tmp:
            fake_clips(project, Path(tmp))
            config, _ = slides.presentation(project, Path(tmp))
            for slide in config.slides:
                streams = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
                     "-of", "csv=p=0", str(slide.file)],
                    capture_output=True, text=True, timeout=30,
                ).stdout.split()
                self.assertIn("audio", streams, slide.file)
                self.assertTrue(Path(slide.rev_file).is_file(), "backward stepping needs the reverse")

    def test_missing_clips_are_a_plain_refusal(self):
        project = deck()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError) as caught:
                slides.presentation(project, Path(tmp))
        self.assertIn("render the deck first", str(caught.exception))

    def test_fragments_are_cached_by_digest(self):
        project = deck()
        with tempfile.TemporaryDirectory() as tmp:
            fake_clips(project, Path(tmp))
            config, _ = slides.presentation(project, Path(tmp))
            stamp = Path(config.slides[0].file).stat().st_mtime_ns
            config2, _ = slides.presentation(project, Path(tmp))
            self.assertEqual(Path(config2.slides[0].file).stat().st_mtime_ns, stamp)

    def test_the_html_deck_is_one_selfcontained_file(self):
        project = deck()
        with tempfile.TemporaryDirectory() as tmp:
            fake_clips(project, Path(tmp))
            html = slides.deck_html(project, Path(tmp))
            text = html.read_text(errors="ignore")
        self.assertIn("Reveal", text)
        self.assertEqual(text.count("data:video/mp4"), 2, "both fragments embedded")


class TestLoopFlag(unittest.TestCase):
    def test_loop_never_moves_the_digest(self):
        """A loop changes playback, not pixels — it must not cost a render."""
        still = Slide(id="s1", component="function_plot", parameters=dict(PLOT))
        looping = Slide(id="s1", component="function_plot", parameters=dict(PLOT), loop=True)
        self.assertEqual(render.digest_of([still]), render.digest_of([looping]))

    def test_the_edit_operation_reaches_the_flag(self):
        from proofmotion.studio.operations import Operation, apply

        project = Project.create("test", "q")
        project.slides = [Slide(id="s1", title="One")]
        apply(project, Operation(kind="edit", slide_id="s1", loop=True))
        self.assertTrue(project.slides[0].loop)
        apply(project, Operation(kind="edit", slide_id="s1", title="Two"))
        self.assertTrue(project.slides[0].loop, "None must mean keep")


if __name__ == "__main__":
    unittest.main()
