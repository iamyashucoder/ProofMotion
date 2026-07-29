from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class MathAnimationState:
    project_id: str
    user_prompt: str
    intent: dict[str, Any] = field(default_factory=dict)
    math_plan: dict[str, Any] = field(default_factory=dict)
    verified_math: dict[str, Any] = field(default_factory=dict)
    pedagogy_plan: dict[str, Any] = field(default_factory=dict)
    storyboard: dict[str, Any] = field(default_factory=dict)
    selected_tools: list[str] = field(default_factory=list)
    render_backend: str = "community"
    render_reason: str = ""
    render_template: str = ""
    tool_results: dict[str, Any] = field(default_factory=dict)
    retrieved_examples: list[dict[str, Any]] = field(default_factory=list)
    generated_code: str = ""
    scene_file: str = ""
    video_file: str = ""
    preview_file: str = ""
    preview_manifest: str = ""
    render_errors: list[str] = field(default_factory=list)
    visual_feedback: list[dict[str, Any]] = field(default_factory=list)
    math_feedback: list[dict[str, Any]] = field(default_factory=list)
    generation_attempt: int = 0
    repair_attempt: int = 0
    llm_provider: str = ""
    llm_model: str = ""
    api_validation: dict[str, Any] = field(default_factory=dict)
    layout_report: dict[str, Any] = field(default_factory=dict)
    typeset_report: dict[str, Any] = field(default_factory=dict)
    components_used: list[str] = field(default_factory=list)
    composed: bool = False
    #: The scene was emitted by the assembler rather than written by the coder.
    assembled: bool = False
    #: Fraction of storyboard scenes a component could express.
    component_coverage: float = 0.0
    #: Fraction that actually draw a picture. equation_chain is a component but
    #: not a picture, so this is the number that says whether a run was visual.
    pictorial_coverage: float = 0.0
    #: What the selector chose, so a fallback to the coder is diagnosable.
    scene_plan: list[dict[str, Any]] = field(default_factory=list)
    recovered_from_tool_calls: bool = False
    wrote_directly: bool = False
    agent_tools_used: dict[str, Any] = field(default_factory=dict)
    token_usage: dict[str, int] = field(default_factory=dict)
    #: Wall-clock seconds per pipeline stage.
    stage_seconds: dict[str, float] = field(default_factory=dict)
    status: str = "created"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, directory: Path) -> Path:
        import json
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "state.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
