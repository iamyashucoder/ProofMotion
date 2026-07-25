"""The ProofMotion pipeline.

Replaces the previous orchestrator, which was a linear function whose behaviour
depended on `if intent.topic == "gradient descent"` and which, without an API
key, emitted a hardcoded gradient-descent scene regardless of what was asked.
Nothing here special-cases a topic, and a missing provider is an error rather
than a silent substitution.
"""

from __future__ import annotations

import ast
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from llm.providers import LLMError, get_client
from proofmotion.agents.coder import write_scene
from proofmotion.agents.debugger import repair_scene
from proofmotion.agents.director import direct_storyboard
from proofmotion.agents.intent import understand_request
from proofmotion.agents.planner import plan_mathematics
from proofmotion.agents.verifier import verify_plan
from proofmotion.runtime.events import BUS, artifact, headline, stage
from proofmotion.runtime.watcher import watch_render
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


def _render_failure(result: Any, output_dir: Path) -> str:
    """Return a failure message, or "" if the render genuinely produced a video.

    Exit code alone is not enough: Manim can exit 0 having written nothing, and
    trusting it once produced a run that reported preview_ready with no video.
    """
    if result.returncode != 0:
        return result.stderr or f"manim exited {result.returncode}"
    if not _find_video(output_dir):
        return "manim exited 0 but produced no video file"
    return ""


def _is_renderable_scene(code: str) -> tuple[bool, str]:
    """Reject code that cannot possibly render.

    tools.code_validator only calls ast.parse, and the empty string parses
    cleanly — which once let an empty file through to a render that produced no
    video while the run reported preview_ready.
    """
    if not code.strip():
        return False, "the coding agent returned no code"
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return False, f"SyntaxError: {error}"
    classes = [n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef)]
    if "GeneratedScene" not in classes:
        return False, f"no GeneratedScene class (found: {classes or 'none'})"
    return True, ""


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
    BUS.emit("run", prompt=user_prompt, project=state.project_id, model=f"{client.name}/{client.model}")

    stage("understand")
    intent = understand_request(client, user_prompt)
    state.intent = intent.model_dump()
    artifact("intent", state.intent)
    headline(f"Read the request as: {intent.topic} ({intent.domain}, {intent.difficulty})")
    if intent.assumptions:
        headline(f"Assumed: {'; '.join(intent.assumptions)}", "warned")
    stage("understand", "done")
    state.save(project_dir)

    stage("plan")
    plan = plan_mathematics(client, intent)
    state.math_plan = plan.model_dump()
    artifact("plan", state.math_plan)
    headline(f"Derived {len(plan.concept_sequence)} mathematical steps using symbolic tools", "improved")
    stage("plan", "done")

    stage("verify")
    state.verified_math = verify_plan(plan)
    checked = sum(1 for c in state.verified_math["checks"] if c.get("equal") is not None)
    artifact("verification", state.verified_math)
    if state.verified_math["valid"]:
        headline(f"All {len(plan.concept_sequence)} steps typeset; {checked} equalities proved by sympy", "improved")
    else:
        # Not fatal: some steps are notation rather than checkable claims. It is
        # recorded so the storyboard knows how much it may assert.
        headline(f"{len(state.verified_math['failures'])} step(s) failed verification", "warned")
    stage("verify", "done")
    state.save(project_dir)

    stage("storyboard")
    storyboard = direct_storyboard(client, intent, plan, state.verified_math)
    state.storyboard = storyboard.model_dump()
    state.selected_tools = ["symbolic", "numeric", "manim_api", "layout", "typeset"]
    artifact("storyboard", state.storyboard)
    headline(f"Composed {len(storyboard.scenes)} scenes, measured against the frame", "improved")
    stage("storyboard", "done")
    state.save(project_dir)

    stage("code")
    written = write_scene(client, state.to_dict())
    state.generated_code = written["code"]
    state.api_validation = written["validation"]
    state.agent_tools_used = written["tools_used"]
    artifact("code", state.generated_code)
    lookups = sum(1 for t in written["tools_used"] if t.startswith("manim_"))
    if written["validation"]["valid"]:
        headline(f"Scene passed API validation after {lookups} Manim lookups", "improved")
    else:
        problems = written["validation"]["problems"]
        headline(f"Scene still has {len(problems)} invalid API call(s): {problems[0].get('problem', '')}", "warned")
    stage("code", "done")

    renderable, why = _is_renderable_scene(state.generated_code)
    if not renderable:
        state.status = "code_validation_failed"
        state.render_errors.append(why)
        headline(f"Stopped: {why}", "warned")
        stage("code", "failed", reason=why)
        state.save(project_dir)
        return state

    valid, error = validate_generated_code(state.generated_code)
    if not valid:
        state.status = "code_validation_failed"
        state.render_errors.append(error or "static validation failed")
        headline(f"Stopped: {error}", "warned")
        state.save(project_dir)
        return state

    scene_file = _save_code(project_dir, state.generated_code)
    state.scene_file = str(scene_file)
    state.preview_manifest = str(write_preview_manifest(project_dir, state.storyboard, scene_file))
    state.status = "draft_ready"
    state.save(project_dir)

    preview_dir = project_dir / "preview"
    stage("render")
    with watch_render(preview_dir):
        preview = render_manim_scene(scene_file, preview_dir, quality="l", timeout_seconds=120)
    render_error = _render_failure(preview, preview_dir)

    if render_error:
        state.render_errors.append(render_error[-4000:])
        headline(f"Render failed: {render_error.strip().splitlines()[-1][:150]}", "warned")
        stage("render", "failed")

        stage("repair")
        repaired = repair_scene(client, state.generated_code, render_error)
        renderable, why = _is_renderable_scene(repaired["code"])
        if renderable:
            state.repair_attempt += 1
            state.generated_code = repaired["code"]
            state.api_validation = repaired["validation"]
            artifact("code", state.generated_code)
            scene_file = _save_code(project_dir, repaired["code"])
            with watch_render(preview_dir, label="repaired"):
                retry = render_manim_scene(scene_file, preview_dir, quality="l", timeout_seconds=120)
            retry_error = _render_failure(retry, preview_dir)
            if not retry_error:
                state.preview_file = _find_video(preview_dir)
                state.status = "preview_ready"
                headline("Repair succeeded; the scene now renders", "fixed")
                stage("repair", "done")
                BUS.emit("video", path=state.preview_file)
                state.save(project_dir)
                return state
            state.render_errors.append(retry_error[-4000:])
        else:
            state.render_errors.append(f"repair unusable: {why}")
        headline("Repair did not produce a renderable scene", "warned")
        stage("repair", "failed")
        state.status = "preview_failed"
        state.save(project_dir)
        return state

    state.preview_file = _find_video(preview_dir)
    state.status = "preview_ready"
    headline("Preview rendered", "improved")
    stage("render", "done")
    BUS.emit("video", path=state.preview_file)
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
