"""The studio's JSON routes: thin parsing around the service, nothing else.

Which project a call is about lives in the URL, not on the server. The old
server kept one "current" project as process state, so two tabs silently
shared it — opening a project in one rerouted the other's next edit.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from proofmotion.studio.operations import MAX_OPERATIONS, Operation
from proofmotion.studio.service import StudioService
from proofmotion.web.schemas import schemas

router = APIRouter(prefix="/api")


def _service(request: Request) -> StudioService:
    return request.app.state.service


class FirstMessage(BaseModel):
    message: str = Field(min_length=1)


class Message(BaseModel):
    message: str = Field(min_length=1)


class Remake(BaseModel):
    slide_id: str
    instruction: str = Field(min_length=1)


class Operations(BaseModel):
    operations: list[Operation] = Field(min_length=1, max_length=MAX_OPERATIONS)


class SlideRef(BaseModel):
    slide_id: str


@router.get("/schemas")
def component_schemas() -> dict[str, Any]:
    return {"schemas": schemas()}


@router.get("/styles")
def styles() -> dict[str, Any]:
    from proofmotion.components.palette import PRESETS
    from proofmotion.studio.render import QUALITIES

    return {
        "styles": [
            {
                "name": p.name,
                "background": p.background,
                "ink": p.ink,
                "colors": [p.accent, p.secondary, p.highlight, p.axis],
            }
            for p in PRESETS.values()
        ],
        "qualities": {
            letter: {"px_w": w, "px_h": h, "fps": fps}
            for letter, (w, h, fps) in QUALITIES.items()
        },
    }


@router.get("/projects")
def projects(request: Request) -> dict[str, Any]:
    return {"projects": _service(request).store.listing()}


@router.post("/projects")
async def create(body: FirstMessage, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_service(request).create_project, body.message.strip())


@router.get("/projects/{project_id}")
async def state(project_id: str, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_service(request).state, project_id)


@router.post("/projects/{project_id}/message")
async def message(project_id: str, body: Message, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(
        _service(request).run_turn, project_id, body.message.strip()
    )


@router.post("/projects/{project_id}/remake")
async def remake(project_id: str, body: Remake, request: Request) -> dict[str, Any]:
    service = _service(request)
    return await asyncio.to_thread(
        lambda: service.run_turn(
            project_id, body.instruction.strip(), remake_slide=body.slide_id
        )
    )


@router.post("/projects/{project_id}/operations")
async def operations(project_id: str, body: Operations, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(
        _service(request).apply_operations, project_id, body.operations
    )


@router.post("/projects/{project_id}/rerender")
async def rerender(project_id: str, body: SlideRef, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_service(request).rerender, project_id, body.slide_id)


class Style(BaseModel):
    style: str


class Quality(BaseModel):
    quality: str


@router.put("/projects/{project_id}/style")
async def set_style(project_id: str, body: Style, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_service(request).set_style, project_id, body.style)


@router.put("/projects/{project_id}/quality")
async def set_quality(project_id: str, body: Quality, request: Request) -> dict[str, Any]:
    return await asyncio.to_thread(_service(request).set_quality, project_id, body.quality)
