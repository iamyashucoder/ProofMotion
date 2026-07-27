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
    given_quantities: list[str] = Field(default_factory=list)
    unknown: str | None = None
    governing_principles: list[str] = Field(default_factory=list)
    #: The direct answer to the question, kept separate from the derivation so
    #: the renderer can always build an unmistakable final-answer scene.
    final_answer_latex: str | None = None
    final_answer_explanation: str | None = None
    requires_symbolic_math: bool = False
    requires_numerical_simulation: bool = False
