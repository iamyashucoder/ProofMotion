from pydantic import BaseModel, Field


class ReviewIssue(BaseModel):
    type: str
    description: str
    severity: str = "warning"


class ReviewResult(BaseModel):
    approved: bool
    math_score: float = Field(ge=0, le=1)
    visual_score: float = Field(ge=0, le=1)
    pedagogy_score: float = Field(ge=0, le=1)
    issues: list[ReviewIssue] = Field(default_factory=list)
