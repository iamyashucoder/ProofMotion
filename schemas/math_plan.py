from pydantic import BaseModel, Field


class MathStep(BaseModel):
    index: int
    concept: str
    equation_latex: str | None = None
    explanation: str
    assumptions: list[str] = Field(default_factory=list)
    connection_to_previous: str | None = None
    requires_verification: bool = True


class MathematicalPlan(BaseModel):
    topic: str
    concept_sequence: list[MathStep]
    requires_symbolic_math: bool = False
    requires_numerical_simulation: bool = False
