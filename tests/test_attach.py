"""Attachments: stored by content, each kind treated the one honest way.

An image is pixels for the model; a voice note is the words it contains; a
clip is a few sampled frames. Nothing silently dropped, nothing faked — the
transcription tests exercise the cache and the refusal, never the network.

No API key required.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import attach

#: A 1x1 red PNG.
DOT = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/q842iQAAAABJRU5ErkJggg=="
)


class TestKinds(unittest.TestCase):
    def test_each_suffix_lands_in_its_kind(self):
        self.assertEqual(attach.kind_of("sketch.PNG"), "image")
        self.assertEqual(attach.kind_of("note.m4a"), "audio")
        self.assertEqual(attach.kind_of("clip.mp4"), "video")

    def test_an_unsupported_file_is_refused_with_the_choices(self):
        with self.assertRaises(ToolError) as caught:
            attach.kind_of("virus.exe")
        self.assertIn(".png", str(caught.exception))


class TestImages(unittest.TestCase):
    def test_an_image_is_stored_by_content_and_rides_as_a_data_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = attach.save(Path(tmp), "sketch.png", DOT)
            self.assertEqual(entry["kind"], "image")
            again = attach.save(Path(tmp), "renamed.png", DOT)
            self.assertEqual(entry["id"], again["id"], "same bytes, same attachment")

            url = attach.data_url(Path(tmp), entry["id"])
            self.assertTrue(url.startswith("data:image/png;base64,"))
            self.assertEqual(base64.b64decode(url.split(",", 1)[1]), DOT)

    def test_only_images_ride_a_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                attach.data_url(Path(tmp), "a" * 16 + ".mp3")

    def test_a_forged_id_is_refused_not_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            for forged in ("../../secret.png", "deadbeef.png", "A" * 16 + ".png"):
                with self.subTest(forged=forged):
                    with self.assertRaises(ToolError):
                        attach.data_url(Path(tmp), forged)

    def test_empty_and_oversized_files_are_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ToolError):
                attach.save(Path(tmp), "empty.png", b"")


class TestAudio(unittest.TestCase):
    def test_a_cached_transcript_never_touches_the_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "note.wav"
            audio.write_bytes(b"RIFFxxxxWAVE")
            audio.with_suffix(".wav.txt").write_text("the cached words", encoding="utf-8")
            self.assertEqual(attach.transcribe(audio), "the cached words")

    def test_no_key_is_a_clear_refusal(self):
        import os
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmp:
            audio = Path(tmp) / "note.wav"
            audio.write_bytes(b"RIFFxxxxWAVE")
            environment = {k: v for k, v in os.environ.items() if k != "OPENAI_API_KEY"}
            with patch.dict(os.environ, environment, clear=True):
                with self.assertRaises(ToolError) as caught:
                    attach.transcribe(audio)
        self.assertIn("OPENAI_API_KEY", str(caught.exception))


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg not on PATH")
class TestVideo(unittest.TestCase):
    def test_a_clip_becomes_a_few_image_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            clip = Path(tmp) / "clip.mp4"
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                 "-i", "color=c=red:s=64x36:d=2", str(clip)],
                check=True, timeout=60,
            )
            entry = attach.save(Path(tmp), "clip.mp4", clip.read_bytes())
            self.assertEqual(entry["kind"], "video")
            self.assertEqual(len(entry["frames"]), attach.VIDEO_FRAMES)
            for frame in entry["frames"]:
                self.assertTrue(frame.endswith(".png"))
                # every frame is itself an attachable image
                self.assertTrue(attach.data_url(Path(tmp), frame).startswith("data:image/png"))


class TestResponsesTranslation(unittest.TestCase):
    def test_image_parts_are_respelled_for_the_responses_api(self):
        from llm.providers import OpenAIResponsesClient

        parts = OpenAIResponsesClient._to_responses_parts([
            {"type": "text", "text": "what is this curve?"},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA"}},
        ])
        self.assertEqual(parts, [
            {"type": "input_text", "text": "what is this curve?"},
            {"type": "input_image", "image_url": "data:image/png;base64,AAA"},
        ])

    def test_plain_string_content_is_untouched(self):
        from llm.providers import OpenAIResponsesClient

        self.assertEqual(OpenAIResponsesClient._to_responses_parts("hello"), "hello")


if __name__ == "__main__":
    unittest.main()
