from pydantic import BaseModel, Field


class AnimationIntent(BaseModel):
    topic: str
    domain: str
    audience: str = "general"
    educational_goal: str
    # Capped at 90: a 60s default produced 36 animations and a 72s video, which
    # is well past where an explanation stops holding attention.
    duration_seconds: int = Field(default=30, ge=5, le=90)
    difficulty: str = "introductory"
    requires_graph: bool = False
    requires_derivation: bool = False
    requires_numerical_simulation: bool = False
    requires_3d: bool = False
    expected_output: str = "animation"
    assumptions: list[str] = Field(default_factory=list)
    clarification_needed: str | None = None
