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
    editable: bool = True

    # `transitions` used to live here. The assembler decides transitions now —
    # it always clears the stage between scenes — so asking the director for
    # them bought nothing and cost output tokens on every storyboard, which is
    # what the director's wall clock is made of.


class Storyboard(BaseModel):
    teaching_strategy: str
    scenes: list[StoryboardScene]
    live_edit_controls: list[str] = Field(default_factory=list)
