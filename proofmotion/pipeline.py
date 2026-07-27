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
from proofmotion.agents.completeness import (
    check_solution_completeness,
    check_storyboard_final_answer,
    ensure_storyboard_final_answer,
)
from proofmotion.agents.debugger import polish_scene, repair_scene
from proofmotion.agents.director import direct_storyboard
from proofmotion.agents.intent import understand_request
from proofmotion.agents.planner import plan_mathematics
from proofmotion.agents.verifier import verify_plan
from proofmotion.compose import (
    assemble,
    coverage,
    pictorial_coverage,
    plan_from_storyboard,
    select_components,
)
from proofmotion.knowledge.answer_oracle import audit_final_answer
from proofmotion.learned import load_all as load_learned
from proofmotion.runtime.events import BUS, artifact, headline, stage
from proofmotion.runtime.registry import ToolError
from proofmotion.runtime.watcher import watch_render
from proofmotion.tools.competitive import competitive_exam_requirements
from proofmotion.tools.creator import study_animation_brief
from proofmotion.tools.inspect_scene import inspect_scene
from proofmotion.tools.manim_api import manim_validate_code
from proofmotion.tools.typeset import typeset_scene
from schemas.state import MathAnimationState
from tools.code_validator import validate_generated_code
from tools.live_preview import write_preview_manifest
from tools.manim_renderer import render_manim_scene

log = logging.getLogger(__name__)
PROJECTS_DIR = Path("generated_projects")

#: How much of a storyboard must actually draw something before assembling it.
#: Measured in pictures, not components: equation_chain is a component, so the
#: first version of this gate passed a run at 0.75 coverage that was four
#: screens of algebra answering a question which asked for full diagrams.
MIN_ASSEMBLY_COVERAGE = 0.5


def _is_competitive_exam_prompt(prompt: str) -> bool:
    """Whether the user explicitly asks for an exam-style, fully worked solution."""
    text = prompt.lower()
    markers = ("jee", "neet", "olympiad", "competitive exam", "entrance exam", "exam question")
    return any(marker in text for marker in markers)


def _is_worked_problem_prompt(prompt: str) -> bool:
    """Recognise a numerical/derivation question even when it does not say JEE."""
    text = prompt.lower()
    requests = ("find ", "calculate", "determine", "derive", "solve", "what is", "how far", "time period", "magnitude", "distance travelled")
    physical_or_math_data = any(char.isdigit() for char in text) or any(token in text for token in ("given", "where ", "force", "mass", "velocity", "voltage", "angle", "equation"))
    # A symbolic derivation can have no numerals or named physical data at all.
    if any(marker in text for marker in ("derive", "solve")):
        return True
    return physical_or_math_data and any(marker in text for marker in requests)


def _is_creator_study_prompt(prompt: str) -> bool:
    text = prompt.lower()
    markers = ("content creator", "study animation", "educational animation", "study purpose", "3blue1brown", "3 blue 1 brown")
    return any(marker in text for marker in markers)


def _repair_against_reference(
    client: Any,
    intent: Any,
    prompt: str,
    plan: Any,
    exam_requirements: dict[str, Any] | None,
) -> tuple[Any, dict[str, Any]]:
    """Reject a result only when an exact, source-attributed reference disagrees.

    This does not alter the normal path for novel questions.  For a matched
    record, the planner gets one focused chance to recompute the concepts,
    physics, and arithmetic.  A remaining disagreement blocks the run before
    it can render an authoritative-looking but contradicted answer.
    """
    audit = audit_final_answer(prompt, plan.final_answer_latex)
    if audit["status"] != "mismatch":
        return plan, audit

    reference = audit["reference"]
    feedback = (
        "A vetted reference-answer audit disagreed with this plan. Recompute every governing principle, "
        "assumption, algebraic transformation, numerical substitution, unit check, and final answer. "
        f"Expected final answer: {reference['answer_latex']}. Source: {reference['source']}. "
        "Do not copy it blindly: derive it and make the last step equal to it."
    )
    headline("Reference answer disagreed; recomputing the full derivation before visualisation", "warned")
    repaired = plan_mathematics(
        client,
        intent,
        exam_requirements=exam_requirements,
        completion_feedback=feedback,
    )
    return repaired, audit_final_answer(prompt, repaired.final_answer_latex)


def _tools_by_agent() -> dict[str, list[str]]:
    """Tool calls so far this run, grouped by the agent that made them."""
    grouped: dict[str, list[str]] = {}
    for event in BUS.history:
        if event.kind == "tool":
            grouped.setdefault(event.data.get("agent", "?"), []).append(event.data["name"])
    return grouped


def _token_usage() -> dict[str, int]:
    total = {"prompt": 0, "completion": 0, "calls": 0}
    for event in BUS.history:
        if event.kind == "usage":
            total["prompt"] += event.data.get("prompt", 0)
            total["completion"] += event.data.get("completion", 0)
            total["calls"] += 1
    return total


def _stage_seconds() -> dict[str, float]:
    """Wall-clock per stage, from the stage boundaries on the bus.

    Runs were known to take ten minutes with no way to say where the time went;
    every event already carried a timestamp, and nothing ever read them.
    """
    opened: dict[str, float] = {}
    elapsed: dict[str, float] = {}
    for event in BUS.history:
        if event.kind != "stage":
            continue
        name = event.data.get("name", "?")
        if event.data.get("status") == "start":
            opened[name] = event.at
        elif name in opened:
            elapsed[name] = round(elapsed.get(name, 0.0) + event.at - opened.pop(name), 1)
    return elapsed


def _save_events(project_dir: Path) -> Path:
    """Persist the run timeline so a slow or surprising run can be read back."""
    import json

    path = project_dir / "events.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for event in BUS.history:
            handle.write(json.dumps(event.as_dict(), default=str) + "\n")
    return path


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
    duration_seconds: int | None = None,
) -> MathAnimationState:
    """Plan, verify, compose, code, and render an animation for any request.

    Wraps the run so its timeline is written out however it ends. The pipeline
    has several exits, and the one worth diagnosing is usually a failure.
    """
    state = _run(
        user_prompt,
        render_final=render_final,
        project_root=project_root,
        provider=provider,
        model=model,
        duration_seconds=duration_seconds,
    )
    try:
        state.stage_seconds = _stage_seconds()
        state.token_usage = state.token_usage or _token_usage()
        directory = project_root / state.project_id
        if directory.is_dir():
            _save_events(directory)
            state.save(directory)
    except OSError as error:  # instrumentation must never fail the run
        log.warning("could not write the run timeline: %s", error)
    return state


def _run(
    user_prompt: str,
    *,
    render_final: bool = False,
    project_root: Path = PROJECTS_DIR,
    provider: str | None = None,
    model: str | None = None,
    duration_seconds: int | None = None,
) -> MathAnimationState:
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
    BUS.reset()
    BUS.emit("run", prompt=user_prompt, project=state.project_id, model=f"{client.name}/{client.model}")

    # Components the system wrote on earlier questions. Registered before
    # anything searches, so they are found the same way built-in ones are.
    remembered = load_learned()
    if remembered:
        headline(f"Loaded {len(remembered)} learned component(s): {', '.join(remembered)}")

    stage("understand")
    intent = understand_request(client, user_prompt)
    worked_problem = _is_worked_problem_prompt(user_prompt)
    if worked_problem:
        intent.requires_derivation = True
    if duration_seconds:
        # An explicit request beats the agent's guess, and every downstream
        # budget is derived from this number.
        intent.duration_seconds = max(5, min(600, duration_seconds))
    state.intent = intent.model_dump()
    artifact("intent", state.intent)
    headline(f"Read the request as: {intent.topic} ({intent.domain}, {intent.difficulty})")
    if intent.assumptions:
        headline(f"Assumed: {'; '.join(intent.assumptions)}", "warned")
    stage("understand", "done")
    state.save(project_dir)

    stage("plan")
    exam_requirements: dict[str, Any] | None = None
    if _is_competitive_exam_prompt(user_prompt) or worked_problem:
        exam_requirements = competitive_exam_requirements(user_prompt)
        state.tool_results["competitive_exam_requirements"] = exam_requirements
        state.selected_tools = exam_requirements["required_tools"]
        artifact("competitive_exam_requirements", exam_requirements)
        headline(
            f"Competitive-exam safeguards: {', '.join(exam_requirements['matched_domains'])}",
            "improved",
        )
    plan = plan_mathematics(client, intent, exam_requirements=exam_requirements)
    completeness = check_solution_completeness(plan, intent)
    if not completeness["complete"]:
        headline("Mathematical plan was incomplete; requesting a full worked solution", "warned")
        plan = plan_mathematics(
            client,
            intent,
            exam_requirements=exam_requirements,
            completion_feedback="; ".join(completeness["problems"]),
        )
        completeness = check_solution_completeness(plan, intent)
    if not completeness["complete"]:
        raise LLMError(f"Mathematical plan is incomplete: {'; '.join(completeness['problems'])}")

    # A reference is only used on an exact local match.  Novel prompts retain
    # the existing symbolic/numeric verification path unchanged.
    plan, reference_audit = _repair_against_reference(
        client, intent, user_prompt, plan, exam_requirements
    )
    if reference_audit["status"] == "mismatch":
        reference = reference_audit["reference"]
        raise LLMError(
            "Final answer conflicts with a vetted reference after a full recomputation: "
            f"derived {plan.final_answer_latex!r}, expected {reference['answer_latex']!r}."
        )
    # A repaired plan must pass the same completeness gate as the original.
    completeness = check_solution_completeness(plan, intent)
    if not completeness["complete"]:
        raise LLMError(f"Reference-repaired mathematical plan is incomplete: {'; '.join(completeness['problems'])}")
    state.tool_results["reference_answer_audit"] = reference_audit
    if reference_audit["status"] == "matched":
        headline("Final answer independently agrees with a vetted reference", "improved")
    elif reference_audit["status"] == "no_reference":
        headline("No exact reference record found; using independent symbolic and numerical checks", "warned")

    state.math_plan = plan.model_dump()
    state.tool_results["solution_completeness"] = completeness
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
    creator_brief: dict[str, Any] | None = None
    if _is_creator_study_prompt(user_prompt):
        creator_brief = study_animation_brief(intent.topic, intent.audience, "concept_explainer")
        state.tool_results["study_animation_brief"] = creator_brief
        state.selected_tools.extend(["study_animation_brief", "study_animation_timing", "motion_design_audit"])
        artifact("study_animation_brief", creator_brief)
        headline("Creator study-animation safeguards enabled", "improved")
    storyboard = direct_storyboard(client, intent, plan, state.verified_math, creator_brief=creator_brief)
    storyboard_completeness = check_storyboard_final_answer(storyboard, plan.final_answer_latex)
    if not storyboard_completeness["complete"]:
        storyboard = ensure_storyboard_final_answer(storyboard, plan.final_answer_latex, plan.final_answer_explanation)
        storyboard_completeness = check_storyboard_final_answer(storyboard, plan.final_answer_latex)
        if not storyboard_completeness["complete"]:
            raise LLMError(f"Storyboard is incomplete: {'; '.join(storyboard_completeness['problems'])}")
        headline("Added the verified final answer to the closing storyboard scene", "improved")
    state.storyboard = storyboard.model_dump()
    state.tool_results["storyboard_completeness"] = storyboard_completeness
    state.selected_tools = list(dict.fromkeys([
        *state.selected_tools,
        "symbolic", "numeric", "manim_api", "layout", "typeset",
    ]))
    artifact("storyboard", state.storyboard)
    headline(f"Composed {len(storyboard.scenes)} scenes, measured against the frame", "improved")
    stage("storyboard", "done")
    state.save(project_dir)

    # Try to assemble the scene from components before asking anyone to write
    # it. When every scene maps onto a component the coder loop is skipped
    # entirely, which is both the reliable path and by far the fast one.
    stage("assemble")
    # The director has already searched for components and built them to check
    # the geometry. When its storyboard names ones that validate, the plan is
    # written and assembly costs nothing; the selector is only for when it does
    # not.
    derived = plan_from_storyboard(state.storyboard)
    if derived is not None:
        selection = {
            "plan": derived,
            "coverage": coverage(derived),
            "problems": [],
            "components": [a.component for a in derived.assignments if a.component],
        }
        headline("Read the scene plan from the storyboard; no extra model call", "improved")
    else:
        selection = select_components(client, state.to_dict())

    state.component_coverage = selection["coverage"]
    assembled_code = ""
    if selection["plan"] is not None:
        scenes = selection["plan"].assignments
        state.scene_plan = [a.model_dump() for a in scenes]
        chosen = selection["components"]
        drawn = pictorial_coverage(selection["plan"])
        state.pictorial_coverage = drawn
        if drawn < MIN_ASSEMBLY_COVERAGE:
            # Assembly is for composing verified pictures. A plan that draws
            # almost nothing is not an assembly job, and accepting one produced
            # exactly the failure it looks like: a question asking for full
            # diagrams answered with screens of algebra, because assembly
            # "succeeded" and the coder — which can draw what no component
            # covers — was never asked.
            headline(
                f"Only {drawn:.0%} of scenes draw anything; the coder will draw this one",
                "warned",
            )
        elif selection["problems"]:
            headline(
                f"Components cover {selection['coverage']:.0%} of scenes; "
                f"{selection['problems'][0][:120]}",
                "warned",
            )
        else:
            try:
                candidate = assemble(selection["plan"])
            except ToolError as error:
                headline(f"Assembly rejected the plan: {error}", "warned")
            else:
                renderable, why = _is_renderable_scene(candidate)
                report = manim_validate_code(candidate) if renderable else {"valid": False}
                if renderable and report["valid"]:
                    assembled_code = candidate
                    state.api_validation = report
                    text_only = len(scenes) - len(chosen)
                    detail = f" and {text_only} equation scene(s)" if text_only else ""
                    headline(
                        f"Assembled {len(scenes)} scenes from verified components"
                        f"{detail}: {', '.join(sorted(set(chosen)))}",
                        "improved",
                    )
                else:
                    # The assembler emitted something the API rejects. That is a
                    # bug here, not the model's, so say so rather than hiding it.
                    headline(
                        f"Assembler output failed validation ({why or 'invalid API call'}); "
                        "falling back to the coder",
                        "warned",
                    )
    else:
        headline("No component plan; the scene will be written by hand", "warned")
    stage("assemble", "done")

    if assembled_code:
        state.generated_code = assembled_code
        state.assembled = True
        state.components_used = sorted(set(selection["components"]))
        # Composed means components carried it. Recording True for an assembly
        # of nothing but equation slides made the demo gallery report success
        # on the runs that most needed looking at.
        state.composed = bool(state.components_used)
        artifact("code", state.generated_code)
    else:
        stage("code")
        written = write_scene(client, state.to_dict())
        state.generated_code = written["code"]
        state.api_validation = written["validation"]
        state.components_used = written.get("components_used", [])
        state.composed = written.get("composed", False)
        state.recovered_from_tool_calls = written.get("recovered_from_tool_calls", False)
        state.wrote_directly = written.get("wrote_directly", False)
        artifact("code", state.generated_code)
        lookups = sum(1 for t in written["tools_used"] if t.startswith("manim_"))
        if state.components_used:
            headline(f"Composed from verified components: {', '.join(state.components_used)}", "improved")
        else:
            headline("No component fitted; the scene was written by hand", "warned")
        if state.wrote_directly:
            headline("The tool loop produced nothing usable; the scene was written on a direct retry", "warned")
        elif state.recovered_from_tool_calls:
            headline("Recovered the scene from the agent's own tool calls", "fixed")
        if written["validation"]["valid"]:
            headline(f"Scene passed API validation after {lookups} Manim lookups", "improved")
        else:
            problems = written["validation"]["problems"]
            headline(f"Scene still has {len(problems)} invalid API call(s): {problems[0].get('problem', '')}", "warned")
        stage("code", "done")

    # Every agent's calls, not only the coder's. Recording just write_scene
    # made it look as though no mathematical tool was ever used, when in
    # truth the planner's calls were simply never written down.
    state.agent_tools_used = _tools_by_agent()

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

    # Compile the notation before rendering. One bad control sequence aborts the
    # whole render minutes in, and adjacent string literals are joined without a
    # space, so a line ending in \quad runs into the next line's first letter.
    stage("typeset")
    tex = typeset_scene(state.generated_code)
    state.typeset_report = tex
    if not tex["ok"]:
        first = tex["problems"][0]
        headline(f"{len(tex['problems'])} LaTeX string(s) do not compile, first at line {first['line']}", "warned")
        repaired = repair_scene(
            client, state.generated_code,
            "The scene does not render because this notation fails to compile:\n"
            + "\n".join(f"  line {q['line']}: {q['expression']} -> {q['error'][:160]}" for q in tex["problems"][:4]),
        )
        renderable, _ = _is_renderable_scene(repaired["code"])
        if renderable and typeset_scene(repaired["code"])["ok"]:
            state.generated_code = repaired["code"]
            state.repair_attempt += 1
            state.typeset_report = typeset_scene(state.generated_code)
            headline("Notation repaired; every string now compiles", "fixed")
        else:
            headline("Could not repair the notation; rendering will likely fail", "warned")
    else:
        headline(f"All {tex['checked']} LaTeX strings compile", "improved")
    stage("typeset", "done")

    # Measure what the code actually puts on screen. The director checked a plan;
    # this checks the scene that was written, which is where overlaps came from.
    stage("layout")
    try:
        report = inspect_scene(state.generated_code)
    except ToolError as error:
        report = {"ok": True, "skipped": str(error)}
        headline(f"Layout check skipped: {error}", "warned")

    if not report.get("ok", True):
        counts = (
            len(report.get("text_overlaps", [])),
            len(report.get("out_of_frame", [])),
            len(report.get("unreadable_text", [])),
        )
        headline(f"Measured {counts[0]} text overlaps, {counts[1]} off-frame, {counts[2]} too small", "warned")
        polished = polish_scene(client, state.generated_code, report)
        renderable, _ = _is_renderable_scene(polished["code"])
        if renderable:
            after = inspect_scene(polished["code"])
            before_total, after_total = sum(counts), (
                len(after.get("text_overlaps", []))
                + len(after.get("out_of_frame", []))
                + len(after.get("unreadable_text", []))
            )
            if after_total < before_total:
                state.generated_code = polished["code"]
                state.api_validation = manim_validate_code(state.generated_code)
                report = after
                headline(f"Layout polished: {before_total} problems down to {after_total}", "fixed")
            else:
                headline(f"Polish did not improve layout ({after_total} vs {before_total}); keeping original", "warned")
    else:
        headline(f"Layout clean across {report.get('beats', 0)} beats", "improved")
    state.layout_report = report
    stage("layout", "done")

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
    state.agent_tools_used = _tools_by_agent()
    state.token_usage = _token_usage()
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
