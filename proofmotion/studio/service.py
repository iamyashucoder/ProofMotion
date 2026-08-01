"""Everything a studio can do to a project, with no HTTP in sight.

The web layer parses requests and serialises answers; this is where the work
happens. One lock per project rather than one for the studio — a turn holds
its project for minutes across model calls and renders, and there is no reason
a second project should wait for it.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Any

from proofmotion.runtime.events import headline, scoped
from proofmotion.runtime.registry import ToolError
from proofmotion.studio import render, turns
from proofmotion.studio.document import Project
from proofmotion.studio.jobs import RenderPool
from proofmotion.studio.operations import Operation, apply_all, touched
from proofmotion.studio.store import ProjectStore

log = logging.getLogger(__name__)

#: What the rendered pixels are, so the page can convert a drag in pixels to a
#: nudge in scene units instead of hard-coding the ratio in its own source.
FRAME = {"width": 14.222, "height": 8.0}


class StudioService:
    """Many projects, a client, and a bounded pool of render workers."""

    def __init__(self, store: ProjectStore, client: Any, pool: RenderPool | None = None) -> None:
        self.store = store
        self.client = client
        self.pool = pool or RenderPool()
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        #: Per-project outcome of the last rebuild: status line, video path,
        #: per-slide errors. Kept here, not on the document — it describes the
        #: projection, and the document must not re-save because of it.
        self._built: dict[str, dict[str, Any]] = {}

    def lock_for(self, project_id: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(project_id, threading.Lock())

    # ---- reading --------------------------------------------------------

    def snapshot(self, project: Project, **extra: Any) -> dict[str, Any]:
        built = self._built.get(project.project_id, {})
        px_w, px_h, _ = render.QUALITIES.get(project.quality, render.QUALITIES["l"])
        return {
            "project_id": project.project_id,
            "revision": project.revision,
            "slides": [s.model_dump() for s in project.slides],
            #: Content-addressed poster keys: a slide whose picture has not
            #: changed keeps its digest, so its thumbnail is never re-fetched.
            "posters": {
                s.id: render.digest_of([s], style=project.style, quality=project.quality)
                for s in project.slides
            },
            "style": project.style,
            "quality": project.quality,
            "video": bool(built.get("video")),
            "status": built.get("status", "Ready."),
            "errors": built.get("errors", {}),
            "partial": built.get("partial", False),
            "resolution": {"px_w": px_w, "px_h": px_h, "frame_w": FRAME["width"], "frame_h": FRAME["height"]},
            **extra,
        }

    def video_path(self, project_id: str) -> str:
        return self._built.get(project_id, {}).get("video", "")

    def state(self, project_id: str) -> dict[str, Any]:
        """The project as it stands, rebuilding its projection on first open.

        Rebuilding is free when nothing changed: every clip is cached, so
        reopening a project costs a concat and no renders at all. Later
        fetches are pure reads.
        """
        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            if project_id not in self._built:
                render.clear_work(self.store.directory(project_id))
                self.rebuild(project)
            return self.snapshot(project, transcript=self.store.transcript(project_id))

    # ---- projects -------------------------------------------------------

    def create_project(self, message: str) -> dict[str, Any]:
        """A new project answering its first message. Nothing exists before
        the first message, so an abandoned "new chat" leaves nothing behind."""
        project = Project.create(self.store.new_id(), "")
        self.store.save(project)
        return self.run_turn(project.project_id, message)

    def new_project(self) -> dict[str, Any]:
        """An empty project, created the moment the person starts attaching.

        The rule stays "nothing exists before the first act" — but dropping a
        picture into the composer is a first act, and it needs somewhere to
        land so it can ride the first message.
        """
        project = Project.create(self.store.new_id(), "")
        self.store.save(project)
        return self.snapshot(project, transcript=[])

    # ---- turns ----------------------------------------------------------

    def run_turn(
        self,
        project_id: str,
        message: str,
        *,
        remake_slide: str = "",
        attachments: list[str] | None = None,
    ) -> dict[str, Any]:
        from proofmotion.studio import attach

        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            directory = self.store.directory(project_id)
            images = [
                attach.data_url(directory, attachment_id)
                for attachment_id in (attachments or [])[: attach.MAX_IMAGES_PER_TURN]
            ]
            kept = [a for a in (attachments or []) if a][: attach.MAX_IMAGES_PER_TURN]
            if remake_slide:
                project.slide(remake_slide)  # raises with a clear message if it is gone
                self.store.remember(
                    project_id, "you", f"↻ {remake_slide}: {message}", attachments=kept
                )
                message = (
                    f"Change only slide {remake_slide}. Leave every other slide exactly as it is. "
                    f"What to change: {message}"
                )
            else:
                if not project.question:
                    project.question = message
                self.store.remember(project_id, "you", message, attachments=kept)
            if images:
                message += f"\n\n[{len(images)} image(s) attached; they are shown to you above.]"

            result = turns.run_turn(
                self.client, project, message, remake_slide=remake_slide, images=images
            )
            if result.refusal:
                return self.snapshot(project, reply=result.refusal)

            edit = result.edit
            outcome = apply_all(project, edit.operations)

            # The picture doctor. A turn that leaves ANY slide wordless gets
            # one pass from the visualizer, whose whole job is finding the
            # function in each slide and drawing it — decks kept shipping as
            # prose because nobody's whole job was the pictures, and the one
            # graph a limit proof needs is worth one more model call.
            applied = list(edit.operations)
            if edit.operations and len(project.slides) >= 3:
                from proofmotion.agents.visualizer import illustrate, undrawn_share

                if undrawn_share(project) > 0:
                    headline("Most slides draw nothing; looking for the pictures in them")
                    try:
                        drawn = illustrate(self.client, project)
                    except Exception as error:  # noqa: BLE001 - the deck ships either way
                        log.info("the visualizer pass failed: %s", error)
                        drawn = None
                    if drawn and drawn.operations:
                        second = apply_all(project, drawn.operations)
                        applied.extend(drawn.operations)
                        outcome["refused"].extend(second["refused"])
                        if second["applied"]:
                            extra = f" Illustrated {second['applied']} slide(s)."
                            edit.reply = (edit.reply + extra) if edit.reply else extra.strip()

            self.store.save(project)
            self.rebuild(project, only=touched(applied))
            reply = edit.reply or f"Applied {outcome['applied']} change(s)."
            self.store.remember(project_id, "bot", reply, [o.model_dump() for o in applied])
            return self.snapshot(
                project,
                reply=reply,
                operations=[o.model_dump() for o in applied],
                refused=outcome["refused"],
            )

    # ---- direct manipulation -------------------------------------------

    def apply_operations(self, project_id: str, operations: list[Operation]) -> dict[str, Any]:
        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            outcome = apply_all(project, operations)
            if outcome["refused"] and not outcome["applied"]:
                return self.snapshot(project, error=outcome["refused"][0]["problem"])
            self.store.save(project)
            # A lock changes no pixels, so it must not invalidate a clip.
            pixels = [op for op in operations if op.kind != "lock"]
            self.rebuild(project, only=touched(pixels) if pixels else [])
            return self.snapshot(project, refused=outcome["refused"])

    def rerender(self, project_id: str, slide_id: str) -> dict[str, Any]:
        """Force one slide's unit through the renderer again."""
        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            project.slide(slide_id)  # raises with a clear message if it is gone
            self.rebuild(project, only=[slide_id])
            return self.snapshot(project)

    def poster(self, project_id: str, slide_id: str):
        project = self.store.load(project_id)
        slide = project.slide(slide_id)
        return self.pool.poster(
            slide, self.store.directory(project_id),
            style=project.style, quality=project.quality,
        )

    # ---- what the person drops in ----------------------------------------

    def save_attachment(self, project_id: str, filename: str, data: bytes) -> dict[str, Any]:
        from proofmotion.studio import attach

        self.store.load(project_id)  # 404/409 mapping; never write under a ghost
        return attach.save(self.store.directory(project_id), filename, data)

    def attachment_file(self, project_id: str, attachment_id: str) -> Path:
        from proofmotion.studio import attach

        suffix = Path(attachment_id).suffix.lower()
        stem = Path(attachment_id).stem
        if suffix not in attach.IMAGE or len(stem) != 16:
            raise ToolError(f"no attachment {attachment_id!r}")
        path = self.store.directory(project_id) / "attachments" / attachment_id
        if not path.is_file():
            raise ToolError(f"no attachment {attachment_id!r}")
        return path

    # ---- speaking -------------------------------------------------------

    def speak(self, project_id: str, slide_id: str) -> dict[str, Any]:
        """One slide's narration as audio, synthesized or straight from cache."""
        from proofmotion.studio import narrate

        project = self.store.load(project_id)
        slide = project.slide(slide_id)
        wav = narrate.synthesize(
            slide.narration,
            project.voice or narrate.DEFAULT_VOICE,
            self.store.directory(project_id),
        )
        return {
            "audio": f"/api/projects/{project_id}/audio/{wav.stem}.wav",
            "seconds": narrate.seconds_of(wav),
        }

    def audio_file(self, project_id: str, digest: str) -> Path:
        path = self.store.directory(project_id) / "audio" / f"{digest}.wav"
        if not path.is_file():
            raise ToolError(f"no audio {digest}")
        return path

    # ---- leaving the studio ---------------------------------------------

    def export_pdf(self, project_id: str):
        """The deck as a PDF of its posters. Poster renders ride the pool."""
        from proofmotion.studio import export

        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            return export.posters_pdf(project, self.store.directory(project_id))

    def export_bundle(self, project_id: str):
        from proofmotion.studio import export

        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            return export.bundle(project, self.store.directory(project_id))

    # ---- the deck's look -------------------------------------------------

    def set_style(self, project_id: str, style: str) -> dict[str, Any]:
        from proofmotion.components.palette import PRESETS

        if style not in PRESETS:
            raise ToolError(f"unknown style {style!r}; available: {sorted(PRESETS)}")
        return self._relook(project_id, style=style)

    def set_quality(self, project_id: str, quality: str) -> dict[str, Any]:
        if quality not in render.QUALITIES:
            raise ToolError(f"unknown quality {quality!r}; available: {sorted(render.QUALITIES)}")
        return self._relook(project_id, quality=quality)

    def _relook(self, project_id: str, **look: str) -> dict[str, Any]:
        """Change how the deck looks; the digests move, so the deck re-renders."""
        with self.lock_for(project_id), scoped(project_id):
            project = self.store.load(project_id)
            for field, value in look.items():
                setattr(project, field, value)
            self.store.save(project)
            self.rebuild(project)
            return self.snapshot(project)

    # ---- rendering ------------------------------------------------------

    def rebuild(self, project: Project, only: list[str] | None = None) -> dict[str, Any]:
        project_id = project.project_id
        if not project.slides:
            self._built[project_id] = {"status": "No slides yet.", "video": "", "errors": {}, "partial": False}
            return {}
        report = render.build(project, self.store.directory(project_id), only=only, run=self.pool.run)
        if report.get("fitted"):
            # fit_narration lengthened slides: a visible edit, so it is saved.
            self.store.save(project)
        summary = (
            f"{len(project.slides)} slides · {report['rendered']} rendered, "
            f"{report['reused']} reused · {report.get('seconds', 0)}s"
        )
        if report["failed"]:
            first = report["problems"][0]
            # The reason, not just the slide. "1 failed on s1" tells nobody
            # anything they can act on, and the reason was already in hand.
            reason = " ".join(str(first["error"]).split())[:180]
            summary += f" · {report['failed']} failed on {','.join(first['slides'])}: {reason}"
        narration = report.get("narration") or {}
        if narration.get("problems"):
            summary += f" · narration: {narration['problems'][0][:120]}"
        elif narration.get("spoken"):
            summary += f" · {narration['spoken']} slide(s) spoken"
        self._built[project_id] = {
            "status": summary,
            "video": report.get("video", ""),
            "errors": report.get("errors", {}),
            "partial": report.get("partial", False),
        }
        headline(summary)
        return report
