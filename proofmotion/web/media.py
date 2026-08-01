"""What the studio streams and serves by the byte: video, posters, events.

The JSON routes live in api.py; this file is everything that is not JSON.
Video goes out as a FileResponse so scrubbing costs a Range request instead of
the whole file in memory. Posters render on the bounded pool, so a filmstrip
asking for twenty at once queues nineteen instead of spawning twenty Manim
processes. The event stream is filtered per project, because the bus is
process-wide and one project's render progress is noise in another's status
line.
"""

from __future__ import annotations

import asyncio
import json
import queue
import re
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse

from proofmotion.runtime.events import BUS
from proofmotion.studio.service import StudioService

router = APIRouter()

#: Seconds between keep-alive comments on a quiet event stream. Without them a
#: proxy or a sleeping laptop kills the connection silently and the page never
#: hears another word.
KEEPALIVE = 15


def _service(request: Request) -> StudioService:
    return request.app.state.service


@router.get("/api/projects/{project_id}/video")
def video(project_id: str, request: Request) -> FileResponse:
    path = _service(request).video_path(project_id)
    if not path or not Path(path).is_file():
        raise HTTPException(404, "no render yet")
    return FileResponse(path, media_type="video/mp4", headers={"Cache-Control": "no-store"})


@router.get("/api/projects/{project_id}/poster/{slide_id}.png")
async def poster(project_id: str, slide_id: str, request: Request) -> FileResponse:
    service = _service(request)
    path = await asyncio.to_thread(service.poster, project_id, slide_id)
    if path is None:
        raise HTTPException(404, "no poster for this slide")
    # The page addresses posters by content digest (?d=...), so a poster can
    # be cached forever: a slide that changes gets a new URL, not a new copy
    # of the old one.
    return FileResponse(path, media_type="image/png",
                        headers={"Cache-Control": "max-age=31536000, immutable"})


@router.get("/api/projects/{project_id}/export/project.json")
def export_document(project_id: str, request: Request) -> FileResponse:
    service = _service(request)
    service.store.load(project_id)  # 404/409 mapping, and never serve a half-written file
    path = service.store.directory(project_id) / "project.json"
    return FileResponse(
        path,
        media_type="application/json",
        filename=f"{project_id}.json",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/projects/{project_id}/export/video.mp4")
def export_video(project_id: str, request: Request) -> FileResponse:
    path = _service(request).video_path(project_id)
    if not path or not Path(path).is_file():
        raise HTTPException(404, "no render yet")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{project_id}.mp4",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/projects/{project_id}/attachments/{attachment_id}")
def attachment(project_id: str, attachment_id: str, request: Request) -> FileResponse:
    path = _service(request).attachment_file(project_id, attachment_id)
    # Content-named, like posters and audio: cacheable forever.
    return FileResponse(path, headers={"Cache-Control": "max-age=31536000, immutable"})


@router.post("/api/projects/{project_id}/slides/{slide_id}/speak")
async def speak(project_id: str, slide_id: str, request: Request) -> dict:
    return await asyncio.to_thread(_service(request).speak, project_id, slide_id)


@router.get("/api/projects/{project_id}/audio/{digest}.wav")
def audio(project_id: str, digest: str, request: Request) -> FileResponse:
    if not re.fullmatch(r"[0-9a-f]{16}", digest):
        raise HTTPException(404, "no such audio")
    path = _service(request).audio_file(project_id, digest)
    # Content-addressed, like posters: the same words in the same voice are
    # the same file forever.
    return FileResponse(path, media_type="audio/wav",
                        headers={"Cache-Control": "max-age=31536000, immutable"})


@router.get("/api/projects/{project_id}/slides/deck.html")
async def slides_html(project_id: str, request: Request) -> FileResponse:
    """The deck as slides you step through — built lazily, cached by content."""
    path = await asyncio.to_thread(_service(request).slides_html, project_id)
    return FileResponse(path, media_type="text/html", headers={"Cache-Control": "no-store"})


@router.get("/api/projects/{project_id}/export/deck.pptx")
async def export_pptx(project_id: str, request: Request) -> FileResponse:
    path = await asyncio.to_thread(_service(request).slides_pptx, project_id)
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=f"{project_id}.pptx",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/projects/{project_id}/export/deck.pdf")
async def export_pdf(project_id: str, request: Request) -> FileResponse:
    # Request-scoped like a turn: the poster sweep can take a while on a long
    # deck the first time, and is a cache hit ever after.
    path = await asyncio.to_thread(_service(request).export_pdf, project_id)
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{project_id}.pdf",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/projects/{project_id}/export/bundle.zip")
async def export_bundle(project_id: str, request: Request) -> FileResponse:
    path = await asyncio.to_thread(_service(request).export_bundle, project_id)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{project_id}.zip",
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/projects/{project_id}/events")
async def events(project_id: str, request: Request) -> StreamingResponse:
    listener = BUS.subscribe(replay=0)

    async def stream():
        try:
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.to_thread(listener.get, True, KEEPALIVE)
                except queue.Empty:
                    yield ": keep-alive\n\n"
                    continue
                if event.data.get("project") != project_id:
                    continue
                yield f"data: {json.dumps(event.as_dict(), default=str)}\n\n"
        finally:
            BUS.unsubscribe(listener)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
