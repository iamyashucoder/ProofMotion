"""The HTTP layer: thin routing, honest status codes, and the front door.

The turn and the renderer are faked; what is under test is that the routes
parse, delegate, and map failures to codes a client can act on — and that a
corrupt document comes back as a 409 with the file untouched, never as an
empty deck.

No API key required. Needs httpx (FastAPI's test client).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

try:
    from fastapi.testclient import TestClient
except ImportError:  # pragma: no cover
    TestClient = None

from proofmotion.studio import Project, Slide
from proofmotion.studio.operations import Edit, Operation
from proofmotion.studio.turns import TurnResult

CLEAN_REPORT = {
    "rendered": 1, "reused": 0, "failed": 0, "problems": [],
    "video": "", "seconds": 6.0, "errors": {}, "partial": False, "units": [],
}


@unittest.skipIf(TestClient is None, "httpx not installed")
class ApiTest(unittest.TestCase):
    def setUp(self):
        from proofmotion.web.app import create_app

        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.app = create_app(self.root, client=None)
        self.http = TestClient(self.app, raise_server_exceptions=False)
        self.service = self.app.state.service

    def tearDown(self):
        self.service.pool.shutdown()
        self._tmp.cleanup()

    def seed(self) -> str:
        project = Project.create(self.service.store.new_id(), "a question")
        project.slides = [Slide(id="s1", title="One")]
        self.service.store.save(project)
        return project.project_id


class TestProjects(ApiTest):
    def test_a_first_message_creates_a_project(self):
        turn = TurnResult(Edit(operations=[Operation(kind="add", title="T")], reply="ok"))
        with (
            patch("proofmotion.studio.turns.run_turn", return_value=turn),
            patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)),
        ):
            response = self.http.post("/api/projects", json={"message": "why"})
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["slides"]), 1)
        self.assertEqual(body["reply"], "ok")
        listing = self.http.get("/api/projects").json()["projects"]
        self.assertEqual([p["id"] for p in listing], [body["project_id"]])

    def test_an_unknown_project_is_a_404(self):
        response = self.http.get("/api/projects/nowhere")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.json())

    def test_a_corrupt_document_is_a_409_and_stays_corrupt(self):
        broken = self.root / "hurt"
        broken.mkdir()
        damage = b'{"project_id": "hurt", "slides": [{'
        (broken / "project.json").write_bytes(damage)

        response = self.http.get("/api/projects/hurt")
        self.assertEqual(response.status_code, 409)
        self.assertIn("not a usable project document", response.json()["error"])
        self.assertEqual((broken / "project.json").read_bytes(), damage)

    def test_state_returns_slides_and_transcript(self):
        pid = self.seed()
        self.service.store.remember(pid, "you", "hello")
        with patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)):
            body = self.http.get(f"/api/projects/{pid}").json()
        self.assertEqual([s["id"] for s in body["slides"]], ["s1"])
        self.assertEqual(body["transcript"][0]["text"], "hello")
        self.assertIn("s1", body["posters"])
        self.assertEqual(body["resolution"]["px_w"], 854)


class TestOperations(ApiTest):
    def test_operations_apply_and_refusals_surface(self):
        pid = self.seed()
        with patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)):
            self.http.get(f"/api/projects/{pid}")
            response = self.http.post(
                f"/api/projects/{pid}/operations",
                json={"operations": [
                    {"kind": "edit", "slide_id": "s1", "title": "Better"},
                    {"kind": "edit", "slide_id": "sX", "title": "Ghost"},
                ]},
            )
        body = response.json()
        self.assertEqual(body["slides"][0]["title"], "Better")
        self.assertEqual(len(body["refused"]), 1)

    def test_a_malformed_body_is_a_422_and_blanks_nothing(self):
        pid = self.seed()
        response = self.http.post(f"/api/projects/{pid}/operations", json={"operations": "no"})
        self.assertEqual(response.status_code, 422)
        self.assertEqual(self.service.store.load(pid).slides[0].title, "One")

    def test_rerender_refuses_a_slide_that_is_gone(self):
        pid = self.seed()
        with patch("proofmotion.studio.render.build", return_value=dict(CLEAN_REPORT)):
            self.http.get(f"/api/projects/{pid}")
            response = self.http.post(
                f"/api/projects/{pid}/rerender", json={"slide_id": "s9"}
            )
        self.assertEqual(response.status_code, 400)
        self.assertIn("no slide", response.json()["error"])


class TestMedia(ApiTest):
    def test_video_serves_ranges(self):
        pid = self.seed()
        video = self.service.store.directory(pid) / "video.mp4"
        video.write_bytes(b"0123456789")
        self.service._built[pid] = {"video": str(video), "status": "", "errors": {}, "partial": False}

        whole = self.http.get(f"/api/projects/{pid}/video")
        self.assertEqual(whole.status_code, 200)
        part = self.http.get(f"/api/projects/{pid}/video", headers={"Range": "bytes=2-5"})
        self.assertEqual(part.status_code, 206)
        self.assertEqual(part.content, b"2345")

    def test_no_video_is_a_404(self):
        pid = self.seed()
        response = self.http.get(f"/api/projects/{pid}/video")
        self.assertEqual(response.status_code, 404)

    def test_the_document_can_be_downloaded(self):
        pid = self.seed()
        response = self.http.get(f"/api/projects/{pid}/export/project.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers.get("content-disposition", ""))


class TestToken(unittest.TestCase):
    @unittest.skipIf(TestClient is None, "httpx not installed")
    def test_the_token_guards_every_route_and_a_cookie_carries_it(self):
        from proofmotion.web.app import create_app

        with tempfile.TemporaryDirectory() as tmp:
            app = create_app(Path(tmp), client=None, token="sesame")
            http = TestClient(app, raise_server_exceptions=False)
            try:
                self.assertEqual(http.get("/api/projects").status_code, 401)
                self.assertEqual(
                    http.get("/api/projects", params={"token": "wrong"}).status_code, 401
                )
                opened = http.get("/api/projects", params={"token": "sesame"})
                self.assertEqual(opened.status_code, 200)
                # The cookie set on that response now carries the session.
                self.assertEqual(http.get("/api/projects").status_code, 200)
            finally:
                app.state.service.pool.shutdown()


if __name__ == "__main__":
    unittest.main()
