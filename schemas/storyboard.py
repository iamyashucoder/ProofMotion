from pydantic import BaseModel, Field


class StoryboardScene(BaseModel):
    scene_id: str
    purpose: str
    #: The heading shown on screen. Distinct from `purpose`, which is a sentence
    #: written for the pipeline — rendered as a title it gets shrunk to fit and
    #: reads as a caption in the wrong place.
    title: str = Field(default="", max_length=60, description="Short on-screen heading, a few words.")
    duration_seconds: float = Field(gt=0, le=60)
    narration: str | None = None
    visual_objects: list[dict] = Field(default_factory=list)
    equations: list[str] = Field(default_factory=list)
    transitions: list[str] = Field(default_factory=list)
    editable: bool = True


class Storyboard(BaseModel):
    teaching_strategy: str
    scenes: list[StoryboardScene]
    live_edit_controls: list[str] = Field(default_factory=list)
