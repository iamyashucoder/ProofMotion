"""Where projects live on disk, and nothing else.

The server used to answer "load this project" with an empty deck whenever the
document could not be read — a project that did not exist yet and a project
whose file was corrupted looked identical, and the next save wrote the empty
deck over the real one. The store's one rule is that those two cases are
different exceptions, and a document it cannot read is a document it will
never touch.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from proofmotion.studio.document import Project


class ProjectNotFound(Exception):
    """No document exists for this project id."""


class ProjectCorrupt(Exception):
    """A document exists and cannot be used. It is never overwritten."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path} is not a usable project document: {reason}")
        self.path = path
        self.reason = reason


def new_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"


class ProjectStore:
    """Many projects under one root directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        #: project id -> (document mtime, listing entry). The rail asks for the
        #: listing on every state fetch, and re-parsing every document in the
        #: root each time grows linearly with history.
        self._listing: dict[str, tuple[float, dict[str, Any]]] = {}
        self._lock = threading.Lock()

    # ---- identity -------------------------------------------------------

    def new_id(self) -> str:
        return new_id()

    def directory(self, project_id: str) -> Path:
        return self.root / project_id

    # ---- documents ------------------------------------------------------

    def load(self, project_id: str) -> Project:
        path = self.directory(project_id) / "project.json"
        if not path.is_file():
            raise ProjectNotFound(project_id)
        try:
            return Project.load(self.directory(project_id))
        except Exception as error:
            raise ProjectCorrupt(path, str(error)) from error

    def save(self, project: Project) -> Path:
        return project.save(self.directory(project.project_id))

    def latest(self) -> str | None:
        found = sorted(
            (p for p in self.root.iterdir() if (p / "project.json").is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        return found[0].name if found else None

    def listing(self) -> list[dict[str, Any]]:
        out = []
        with self._lock:
            for path in sorted(self.root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
                document = path / "project.json"
                if not document.is_file():
                    continue
                try:
                    mtime = document.stat().st_mtime
                except OSError:
                    continue
                cached = self._listing.get(path.name)
                if cached and cached[0] == mtime:
                    out.append(cached[1])
                    continue
                try:
                    raw = json.loads(document.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                entry = {
                    "id": path.name,
                    "title": (raw.get("question") or "Untitled")[:52],
                    "slides": len(raw.get("slides") or []),
                    "when": (raw.get("created_at") or "")[:10],
                }
                self._listing[path.name] = (mtime, entry)
                out.append(entry)
        return out

    # ---- the conversation -----------------------------------------------

    def transcript(self, project_id: str) -> list[dict[str, Any]]:
        """What was said in a project, so switching back shows the thread."""
        path = self.directory(project_id) / "transcript.json"
        if not path.is_file():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

    def remember(
        self, project_id: str, who: str, text: str, operations: list | None = None
    ) -> None:
        path = self.directory(project_id) / "transcript.json"
        thread = self.transcript(project_id)
        thread.append({"who": who, "text": text, "operations": operations or []})
        path.parent.mkdir(parents=True, exist_ok=True)
        scratch = path.with_name(path.name + ".tmp")
        scratch.write_text(json.dumps(thread[-80:], default=str), encoding="utf-8")
        os.replace(scratch, path)
