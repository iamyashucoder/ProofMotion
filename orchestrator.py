from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from agents.debug_agent import repair_code
from agents.intent_agent import run_intent_agent
from agents.manim_coder import run_manim_coder
from agents.math_planner import run_math_planner
from agents.math_verifier import run_math_verifier
from agents.pedagogy_agent import run_pedagogy_agent
from agents.tool_router import select_tools
from agents.visual_director import run_visual_director
from llm.gemma_client import GemmaClient
from schemas.state import MathAnimationState
from tools.code_validator import validate_generated_code
from tools.live_preview import write_preview_manifest
from tools.manim_renderer import render_manim_scene
from tools.numerical_math import gradient_descent_sequence


PROJECTS_DIR = Path("generated_projects")


def _project_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"


def _save_code(project_dir: Path, code: str) -> Path:
    path = project_dir / "generated_scene.py"
    path.write_text(code, encoding="utf-8")
    return path


def _find_video(output_dir: Path) -> str:
    videos = list(output_dir.rglob("*.mp4"))
    return str(videos[0]) if videos else ""


def create_math_animation(user_prompt: str, *, render_final: bool = False, project_root: Path = PROJECTS_DIR) -> MathAnimationState:
    """Build a reviewable draft first; final video rendering is opt-in."""
    state = MathAnimationState(project_id=_project_id(), user_prompt=user_prompt)
    project_dir = project_root / state.project_id
    project_dir.mkdir(parents=True, exist_ok=False)

    intent = run_intent_agent(user_prompt)
    plan = run_math_planner(intent)
    verified = run_math_verifier(plan)
    pedagogy = run_pedagogy_agent(intent, verified)
    storyboard = run_visual_director(intent, verified, pedagogy)
    state.intent = intent.model_dump()
    state.math_plan = plan.model_dump()
    state.verified_math = verified
    state.pedagogy_plan = pedagogy
    state.storyboard = storyboard.model_dump()
    state.selected_tools = select_tools(intent, state.math_plan)
    if intent.topic == "gradient descent":
        state.tool_results["gradient_descent"] = gradient_descent_sequence(-2, 0.2, 7, lambda x: 2 * (x - 2))

    client = GemmaClient()
    llm = client if client.available else None
    state.generated_code = run_manim_coder(llm, state.to_dict())
    valid, error = validate_generated_code(state.generated_code)
    if not valid:
        state.status = "code_validation_failed"
        state.render_errors.append(error or "Unknown static validation error")
        state.save(project_dir)
        return state

    scene_file = _save_code(project_dir, state.generated_code)
    state.scene_file = str(scene_file)
    state.preview_manifest = str(write_preview_manifest(project_dir, state.storyboard, scene_file))
    state.status = "draft_ready"
    state.save(project_dir)

    # A low-quality render is a checkpoint for human editing, not a final deliverable.
    preview_dir = project_dir / "preview"
    preview = render_manim_scene(scene_file, preview_dir, quality="l", timeout_seconds=90)
    if preview.returncode != 0:
        state.render_errors.append(preview.stderr)
        fixed = repair_code(llm, user_prompt, state.generated_code, preview.stderr)
        if fixed:
            valid, error = validate_generated_code(fixed)
            if valid:
                state.repair_attempt += 1
                state.generated_code = fixed
                scene_file = _save_code(project_dir, fixed)
                retry = render_manim_scene(scene_file, preview_dir, quality="l", timeout_seconds=90)
                if retry.returncode != 0:
                    state.render_errors.append(retry.stderr)
                else:
                    state.preview_file = _find_video(preview_dir)
            else:
                state.render_errors.append(error or "Repair failed static validation")
        state.status = "preview_failed"
        state.save(project_dir)
        return state

    state.preview_file = _find_video(preview_dir)
    state.status = "preview_ready"
    state.save(project_dir)
    if not render_final:
        return state

    final_dir = project_dir / "final"
    final = render_manim_scene(scene_file, final_dir, quality="h", timeout_seconds=180)
    if final.returncode == 0:
        state.video_file = _find_video(final_dir)
        state.status = "final_ready"
    else:
        state.render_errors.append(final.stderr)
        state.status = "final_failed"
    state.save(project_dir)
    return state
