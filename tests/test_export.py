"""Export: the PDF and the zip, complete or refused — never silently thinner.

Poster renders are faked with synthesized PNGs; what is under test is the
assembly, the content-keyed caching, and the refusal to ship a partial deck.

No API key required.
"""

from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import Project, Slide, render
from proofmotion.studio.export import bundle, deck_digest, posters_pdf

PLOT = {"expr": "x**2", "x_min": 0.0, "x_max": 3.0}


def deck(n: int = 3) -> Project:
    project = Project.create("test", "q")
    project.slides = [
        Slide(id=f"s{i}", title=f"Slide {i}", component="function_plot",
              parameters={**PLOT, "x_max": float(i + 1)})
        for i in range(1, n + 1)
    ]
    return project


def fake_posters(directory: Path):
    """A poster 'renderer' that draws a solid PNG where manim would."""
    from PIL import Image

    def poster(slide, directory_, *, style="dark", quality="l"):
        path = render.poster_path(slide, directory_, style=style, quality=quality)
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (64, 36), "#224466").save(path)
        return path

    return patch("proofmotion.studio.render.poster", side_effect=poster)


class TestDeckDigest(unittest.TestCase):
    def test_stable_until_the_content_moves(self):
        project = deck()
        first = deck_digest(project)
        self.assertEqual(first, deck_digest(project))
        project.slides[1].parameters = {**PLOT, "x_max": 9.0}
        self.assertNotEqual(first, deck_digest(project))

    def test_a_restyle_is_a_new_deck(self):
        project = deck()
        first = deck_digest(project)
        project.style = "paper"
        self.assertNotEqual(first, deck_digest(project))


class TestPdf(unittest.TestCase):
    def test_one_page_per_slide_in_order(self):
        project = deck(3)
        with tempfile.TemporaryDirectory() as tmp, fake_posters(Path(tmp)):
            pdf = posters_pdf(project, Path(tmp))
            self.assertTrue(pdf.name.startswith("deck-"))
            content = pdf.read_bytes()
        self.assertTrue(content.startswith(b"%PDF"))
        # One page object per slide; "/Type /Pages" is the catalogue, not a page.
        pages = content.count(b"/Type /Page") - content.count(b"/Type /Pages")
        self.assertEqual(pages, 3)

    def test_a_missing_poster_refuses_the_whole_pdf(self):
        """A silently thinner deck reads as complete to whoever receives it."""
        project = deck(2)

        def broken(slide, directory, *, style="dark", quality="l"):
            return None

        with tempfile.TemporaryDirectory() as tmp:
            with patch("proofmotion.studio.render.poster", side_effect=broken):
                with self.assertRaises(ToolError) as caught:
                    posters_pdf(project, Path(tmp))
            self.assertIn("s1", str(caught.exception))
            self.assertEqual(list(Path(tmp).rglob("*.pdf")), [])

    def test_the_pdf_is_cached_by_content(self):
        project = deck(2)
        with tempfile.TemporaryDirectory() as tmp, fake_posters(Path(tmp)):
            first = posters_pdf(project, Path(tmp))
            stamp = first.stat().st_mtime_ns
            second = posters_pdf(project, Path(tmp))
            self.assertEqual(first, second)
            self.assertEqual(stamp, second.stat().st_mtime_ns)


class TestBundle(unittest.TestCase):
    def test_the_zip_holds_exactly_the_three_artifacts(self):
        project = deck(2)
        with tempfile.TemporaryDirectory() as tmp, fake_posters(Path(tmp)):
            directory = Path(tmp)
            (directory / "video.mp4").write_bytes(b"the film")
            project.save(directory)
            archive = bundle(project, directory)
            with zipfile.ZipFile(archive) as z:
                self.assertEqual(sorted(z.namelist()), ["deck.pdf", "project.json", "video.mp4"])

    def test_no_video_refuses_the_bundle(self):
        project = deck(1)
        with tempfile.TemporaryDirectory() as tmp, fake_posters(Path(tmp)):
            with self.assertRaises(ToolError) as caught:
                bundle(project, Path(tmp))
        self.assertIn("video", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
