"""The ProofMotion pipeline.

Replaces the previous orchestrator, which was a linear function whose behaviour
depended on `if intent.topic == "gradient descent"` and which, without an API
key, emitted a hardcoded gradient-descent scene regardless of what was asked.
Nothing here special-cases a topic, and a missing provider is an error rather
than a silent substitution.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from llm.providers import LLMError, get_client
from proofmotion.agents.coder import write_scene
from proofmotion.agents.debugger import repair_scene
from proofmotion.agents.director import direct_storyboard
from proofmotion.agents.intent import understand_request
from proofmotion.agents.planner import plan_mathematics
from proofmotion.agents.verifier import verify_plan
from schemas.state import MathAnimationState
from tools.code_validator import validate_generated_code
from tools.live_preview import write_preview_manifest
from tools.manim_renderer import render_manim_scene

log = logging.getLogger(__name__)
PROJECTS_DIR = Path("generated_projects")


def _project_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"


def _save_code(project_dir: Path, code: str) -> Path:
    path = project_dir / "generated_scene.py"
    path.write_text(code, encoding="utf-8")
    return path


def _find_video(output_dir: Path) -> str:
    videos = [p for p in output_dir.rglob("*.mp4") if "partial_movie_files" not in p.parts]
    return str(videos[0]) if videos else ""


def create_math_animation(
    user_prompt: str,
    *,
    render_final: bool = False,
    project_root: Path = PROJECTS_DIR,
    provider: str | None = None,
    model: str | None = None,
) -> MathAnimationState:
    """Plan, verify, compose, code, and render an animation for any request."""
    client = get_client(provider, model)
    if client is None:
        raise LLMError(
            "No LLM provider is configured. Set DEEPSEEK_API_KEY or OPENROUTER_API_KEY "
            "and select one with PROOFMOTION_LLM_PROVIDER. There is no offline path: "
            "a canned animation would not answer the question that was asked."
        )

    state = MathAnimationState(project_id=_project_id(), user_prompt=user_prompt)
    state.llm_provider, state.llm_model = client.name, client.model
    project_dir = project_root / state.project_id
    project_dir.mkdir(parents=True, exist_ok=False)

    log.info("understanding request")
    intent = understand_request(client, user_prompt)
    state.intent = intent.model_dump()
    state.save(project_dir)

    log.info("planning mathematics for %r", intent.topic)
    plan = plan_mathematics(client, intent)
    state.math_plan = plan.model_dump()

    log.info("verifying %d steps", len(plan.concept_sequence))
    state.verified_math = verify_plan(plan)
    if not state.verified_math["valid"]:
        # Not fatal: some steps are notation rather than checkable claims. It is
        # recorded so the storyboard knows how much it may assert.
        log.warning("verification found %d problem(s)", len(state.verified_math["failures"]))
    state.save(project_dir)

    log.info("directing storyboard")
    storyboard = direct_storyboard(client, intent, plan, state.verified_math)
    state.storyboard = storyboard.model_dump()
    state.selected_tools = ["symbolic", "numeric", "manim_api", "layout", "typeset"]
    state.save(project_dir)

    log.info("writing scene")
    written = write_scene(client, state.to_dict())
    state.generated_code = written["code"]
    state.api_validation = written["validation"]
    state.agent_tools_used = written["tools_used"]
    if not written["validation"]["valid"]:
        log.warning("scene failed API validation: %s", written["validation"]["problems"][:3])

    valid, error = validate_generated_code(state.generated_code)
    if not valid:
        state.status = "code_validation_failed"
        state.render_errors.append(error or "static validation failed")
        state.save(project_dir)
        return state

    scene_file = _save_code(project_dir, state.generated_code)
    state.scene_file = str(scene_file)
    state.preview_manifest = str(write_preview_manifest(project_dir, state.storyboard, scene_file))
    state.status = "draft_ready"
    state.save(project_dir)

    preview_dir = project_dir / "preview"
    preview = render_manim_scene(scene_file, preview_dir, quality="l", timeout_seconds=120)

    if preview.returncode != 0:
        state.render_errors.append(preview.stderr[-4000:])
        log.info("render failed; attempting repair")
        repaired = repair_scene(client, state.generated_code, preview.stderr)
        if repaired["code"]:
            ok, static_error = validate_generated_code(repaired["code"])
            if ok:
                state.repair_attempt += 1
                state.generated_code = repaired["code"]
                state.api_validation = repaired["validation"]
                scene_file = _save_code(project_dir, repaired["code"])
                retry = render_manim_scene(scene_file, preview_dir, quality="l", timeout_seconds=120)
                if retry.returncode == 0:
                    state.preview_file = _find_video(preview_dir)
                    state.status = "preview_ready"
                    state.save(project_dir)
                    return state
                state.render_errors.append(retry.stderr[-4000:])
            else:
                state.render_errors.append(static_error or "repair failed static validation")
        state.status = "preview_failed"
        state.save(project_dir)
        return state

    state.preview_file = _find_video(preview_dir)
    state.status = "preview_ready"
    state.save(project_dir)
    if not render_final:
        return state

    final_dir = project_dir / "final"
    final = render_manim_scene(scene_file, final_dir, quality="h", timeout_seconds=300)
    if final.returncode == 0:
        state.video_file = _find_video(final_dir)
        state.status = "final_ready"
    else:
        state.render_errors.append(final.stderr[-4000:])
        state.status = "final_failed"
    state.save(project_dir)
    return state
