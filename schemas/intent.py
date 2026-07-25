from pydantic import BaseModel, Field


class AnimationIntent(BaseModel):
    topic: str
    domain: str
    audience: str = "general"
    educational_goal: str
    duration_seconds: int = Field(default=30, ge=5, le=180)
    difficulty: str = "introductory"
    requires_graph: bool = False
    requires_derivation: bool = False
    requires_numerical_simulation: bool = False
    requires_3d: bool = False
    expected_output: str = "animation"
    assumptions: list[str] = Field(default_factory=list)
    clarification_needed: str | None = None
