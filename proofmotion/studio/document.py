"""The project document: an ordered list of slides that outlives any one run.

The pipeline was a function — prompt in, video out, nothing kept. A follow-up
question could not extend the video because there was nothing to extend, only
code to run again from the top. That is what made every answer cost a full
render and made every small change a total redo.

So the document is the artifact and the video is a projection of it. Adding a
slide adds a slide; the ones already rendered are not touched, not re-derived,
and not re-checked. Everything downstream depends on that being literally true,
which is why slide ids are stable and why nothing here regenerates anything.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from proofmotion.compose.assembler import SceneAssignment, ScenePlan
from proofmotion.runtime.registry import ToolError


class Slide(BaseModel):
    """One scene, and the identity that lets it be edited without a redo."""

    #: Stable for the life of the slide. It is the cache key, so renumbering
    #: on reorder would silently re-render a video that had not changed.
    id: str
    title: str = ""
    component: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    caption: str = ""
    seconds: float = Field(default=6.0, gt=0.5, le=40.0)
    #: Hand placement applied after the layout engine. See PLAN-STUDIO §7.
    overrides: dict[str, Any] = Field(default_factory=dict)
    #: Manim written for this slide when nothing in the catalogue fits. The
    #: studio could only compose components, so a request to animate a square
    #: morphing into a circle produced an honest refusal and no slides at all —
    #: while the pipeline it replaced would have drawn it.
    code: str = ""
    #: "agent" or "human" — who last set this slide.
    origin: str = "agent"
    #: A slide the person has settled. An agent may propose, never overwrite.
    locked: bool = False

    def as_assignment(self) -> SceneAssignment:
        """The form the assembler already understands."""
        return SceneAssignment(
            title=self.title,
            component=self.component,
            parameters=self.parameters,
            caption=self.caption,
            seconds=self.seconds,
            overrides=self.overrides,
        )


class Project(BaseModel):
    """A question and the slides answering it, so far."""

    project_id: str
    question: str = ""
    revision: int = 0
    created_at: str = ""
    slides: list[Slide] = Field(default_factory=list)

    # ---- identity -------------------------------------------------------

    def next_id(self) -> str:
        """A fresh slide id that no existing or deleted slide has held.

        Counting the slides would reuse an id after a deletion, and a reused id
        collides with the cached clip of the slide that is gone — the new slide
        would render as the old one.
        """
        used = {s.id for s in self.slides}
        index = len(used) + 1
        while f"s{index}" in used:
            index += 1
        return f"s{index}"

    def slide(self, slide_id: str) -> Slide:
        for slide in self.slides:
            if slide.id == slide_id:
                return slide
        raise ToolError(f"no slide {slide_id!r}; have {[s.id for s in self.slides]}")

    def index_of(self, slide_id: str) -> int:
        for position, slide in enumerate(self.slides):
            if slide.id == slide_id:
                return position
        raise ToolError(f"no slide {slide_id!r}; have {[s.id for s in self.slides]}")

    # ---- projection -----------------------------------------------------

    def as_plan(self) -> ScenePlan:
        """The whole document as a scene plan, for checking or a full render."""
        if not self.slides:
            raise ToolError("the project has no slides yet")
        return ScenePlan(assignments=[s.as_assignment() for s in self.slides])

    def seconds(self) -> float:
        return round(sum(s.seconds for s in self.slides), 1)

    # ---- persistence ----------------------------------------------------

    @classmethod
    def create(cls, project_id: str, question: str = "") -> Project:
        return cls(
            project_id=project_id,
            question=question,
            created_at=f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}",
        )

    @classmethod
    def load(cls, directory: Path) -> Project:
        path = Path(directory) / "project.json"
        if not path.is_file():
            raise ToolError(f"no project document at {path}")
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as error:
            # Never coerce. A document that no longer validates is a project
            # whose components moved under it, and silently repairing it would
            # produce a video nobody asked for.
            raise ToolError(f"{path} is not a usable project document: {error}") from error

    def save(self, directory: Path) -> Path:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "project.json"
        path.write_text(json.dumps(self.model_dump(), indent=2), encoding="utf-8")
        return path
