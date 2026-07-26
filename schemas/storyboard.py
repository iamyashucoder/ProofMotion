from pydantic import BaseModel, Field


class StoryboardScene(BaseModel):
    scene_id: str
    purpose: str
    duration_seconds: float = Field(gt=0)
    narration: str | None = None
    visual_objects: list[dict] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)
    editable: bool = True


class Storyboard(BaseModel):
    teaching_strategy: str
    scenes: list[StoryboardScene]
    live_edit_controls: list[str] = Field(default_factory=list)
