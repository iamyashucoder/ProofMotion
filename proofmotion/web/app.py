"""Assemble the studio: service, routes, static page, and the front door.

Turns run in worker threads (`asyncio.to_thread` in the routes), so the event
loop stays free while a turn spends minutes on model calls and renders; only
turns on the *same* project queue behind each other, on the service's
per-project lock.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from proofmotion.runtime.registry import ToolError
from proofmotion.studio.jobs import DEFAULT_WORKERS, RenderPool
from proofmotion.studio.service import StudioService
from proofmotion.studio.store import ProjectCorrupt, ProjectNotFound, ProjectStore
from proofmotion.web import api, media

STATIC = Path(__file__).parent / "static"

#: What a browser without the token sees: a door, not a diagnostic.
GATE = """<!doctype html>
<meta charset="utf-8"><title>ProofMotion Studio</title>
<body style="font-family:system-ui;background:#0d1117;color:#e6edf3;display:grid;place-items:center;height:100vh;margin:0">
<form style="text-align:center">
  <h1 style="font-weight:600">ProofMotion Studio</h1>
  <p style="color:#8b949e">This studio is token-protected off its own machine.<br>
  Paste the token printed where it was started.</p>
  <input name="token" autofocus placeholder="token"
         style="padding:.5em .8em;border-radius:6px;border:1px solid #26303d;background:#161b22;color:#e6edf3">
  <button style="padding:.5em 1em;border-radius:6px;border:0;background:#4aa3df;color:#0d1117;font-weight:600">Open</button>
</form>
</body>"""


def create_app(
    root: Path,
    client: Any,
    *,
    token: str | None = None,
    render_workers: int = DEFAULT_WORKERS,
) -> FastAPI:
    root = Path(root)
    # Pointed at a project rather than a root, treat its parent as the root so
    # the explorer still shows its siblings.
    if (root / "project.json").is_file():
        root = root.parent

    app = FastAPI(title="ProofMotion Studio", docs_url=None, redoc_url=None)
    app.state.service = StudioService(ProjectStore(root), client, RenderPool(render_workers))
    app.state.token = token

    @app.exception_handler(ToolError)
    async def tool_error(request: Request, error: ToolError) -> JSONResponse:
        return JSONResponse({"error": str(error)[:400]}, status_code=400)

    @app.exception_handler(ProjectNotFound)
    async def not_found(request: Request, error: ProjectNotFound) -> JSONResponse:
        return JSONResponse({"error": f"no project {error}"}, status_code=404)

    @app.exception_handler(ProjectCorrupt)
    async def corrupt(request: Request, error: ProjectCorrupt) -> JSONResponse:
        # The document is damaged and stays exactly as it is on disk; the one
        # thing the server must never do here is answer with an empty deck.
        return JSONResponse({"error": str(error)}, status_code=409)

    @app.exception_handler(Exception)
    async def failed(request: Request, error: Exception) -> JSONResponse:
        return JSONResponse({"error": str(error)[:400]}, status_code=500)

    if token:
        # The studio executes generated Manim; off loopback it must not be an
        # open endpoint. The token guards other machines only — you, on the
        # machine it runs on, are who the studio belongs to, and answering
        # localhost with "unauthorized" reads as the studio being down. The
        # token rides the first URL (?token=...), then a cookie carries it so
        # images, video and the event stream all pass; a browser without it
        # gets a page that asks, not a line of JSON.
        @app.middleware("http")
        async def guard(request: Request, call_next):
            peer = request.client.host if request.client else ""
            supplied = (
                request.headers.get("authorization", "").removeprefix("Bearer").strip()
                or request.query_params.get("token")
                or request.cookies.get("pm_token")
            )
            if supplied != token and peer not in ("127.0.0.1", "::1"):
                if "text/html" in request.headers.get("accept", ""):
                    return HTMLResponse(GATE, status_code=401)
                return JSONResponse({"error": "unauthorized"}, status_code=401)
            response = await call_next(request)
            if request.query_params.get("token") == token:
                response.set_cookie("pm_token", token, httponly=True, samesite="strict")
            return response

    app.include_router(api.router)
    app.include_router(media.router)

    @app.get("/p/{project_id}")
    async def deep_link(project_id: str) -> FileResponse:
        return FileResponse(STATIC / "index.html", headers={"Cache-Control": "no-store"})

    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
    return app
