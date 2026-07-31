"""The store's one rule: a document it cannot read is a document it never touches.

The old server answered every unreadable project with a fresh empty one, and
the next save wrote that emptiness over the real deck. These tests hold the
two cases apart — missing is normal, corrupt is an error — and hold saves to
being atomic, so a crash mid-write can never produce the corrupt case.

No API key required.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from proofmotion.studio import Project, Slide
from proofmotion.studio.store import ProjectCorrupt, ProjectNotFound, ProjectStore


class TestLoad(unittest.TestCase):
    def test_a_missing_project_is_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            with self.assertRaises(ProjectNotFound):
                store.load("nowhere")

    def test_a_corrupt_document_raises_and_is_left_exactly_as_it_was(self):
        """Corruption must reach the person, never become an empty deck."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            broken = store.directory("hurt")
            broken.mkdir()
            damage = b'{"project_id": "hurt", "slides": [{"no such": '
            (broken / "project.json").write_bytes(damage)

            with self.assertRaises(ProjectCorrupt):
                store.load("hurt")
            store.listing()  # any other store call is equally hands-off
            self.assertEqual((broken / "project.json").read_bytes(), damage)

    def test_a_saved_project_loads_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            project = Project.create(store.new_id(), "why is the sky blue")
            project.slides = [Slide(id="s1", title="Rayleigh")]
            store.save(project)
            back = store.load(project.project_id)
        self.assertEqual([s.title for s in back.slides], ["Rayleigh"])


class TestAtomicWrites(unittest.TestCase):
    def test_a_save_leaves_no_scratch_file_behind(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            project = Project.create("p1", "q")
            store.save(project)
            names = {p.name for p in store.directory("p1").iterdir()}
        self.assertEqual(names, {"project.json"})

    def test_a_crashed_writer_cannot_hurt_the_document(self):
        """A writer that died mid-save leaves a scratch file, not damage."""
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            project = Project.create("p1", "the real question")
            store.save(project)
            # The moment before the crash: a half-written scratch file exists.
            (store.directory("p1") / "project.json.tmp").write_text('{"half": ', encoding="utf-8")
            back = store.load("p1")
        self.assertEqual(back.question, "the real question")

    def test_the_transcript_is_written_the_same_way(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            store.remember("p1", "you", "hello")
            store.remember("p1", "bot", "hi", [{"kind": "add"}])
            names = {p.name for p in store.directory("p1").iterdir()}
            self.assertEqual(names, {"transcript.json"})
            thread = store.transcript("p1")
        self.assertEqual([t["who"] for t in thread], ["you", "bot"])
        self.assertEqual(thread[1]["operations"], [{"kind": "add"}])


class TestListing(unittest.TestCase):
    def test_the_listing_reflects_what_is_on_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            project = Project.create("p1", "a question about circles")
            project.slides = [Slide(id="s1"), Slide(id="s2")]
            store.save(project)
            entries = store.listing()
        self.assertEqual([e["id"] for e in entries], ["p1"])
        self.assertEqual(entries[0]["slides"], 2)
        self.assertEqual(entries[0]["title"], "a question about circles")

    def test_the_cache_notices_a_document_that_changed(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            project = Project.create("p1", "before")
            store.save(project)
            store.listing()

            project.question = "after"
            path = store.save(project)
            # Filesystem mtime granularity can make back-to-back writes look
            # simultaneous; move the clock forward explicitly.
            stat = path.stat()
            os.utime(path, (stat.st_atime, stat.st_mtime + 2))

            entries = store.listing()
        self.assertEqual(entries[0]["title"], "after")

    def test_the_cache_serves_an_unchanged_document_without_rereading(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = ProjectStore(Path(tmp))
            store.save(Project.create("p1", "steady"))
            first = store.listing()
            # If this reparsed the file it would fail; the entry must come
            # from the cache once the mtime is unchanged.
            document = store.directory("p1") / "project.json"
            stat = document.stat()
            document.write_bytes(b"not json at all")
            os.utime(document, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            second = store.listing()
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
