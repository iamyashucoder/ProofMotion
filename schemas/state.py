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
    recovered_from_tool_calls: bool = False
    wrote_directly: bool = False
    agent_tools_used: list[str] = field(default_factory=list)
    status: str = "created"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def save(self, directory: Path) -> Path:
        import json
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "state.json"
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        return path
