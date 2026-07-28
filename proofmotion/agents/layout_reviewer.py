"""A strict pre-render gate for text readability and collision repair."""

from __future__ import annotations

from typing import Any

from proofmotion.agents.debugger import polish_scene
from proofmotion.runtime.registry import ToolError
from proofmotion.tools.inspect_scene import inspect_scene
from proofmotion.tools.manim_api import manim_validate_code


def text_layout_issue_count(report: dict[str, Any]) -> int:
    """Count every layout problem that makes text unreadable or misleading."""
    return sum(
        len(report.get(key, []))
        for key in ("text_overlaps", "out_of_frame", "unreadable_text", "text_on_ink")
    )


def validate_and_repair_text_layout(
    client: Any, code: str, *, max_repairs: int = 2
) -> dict[str, Any]:
    """Require clean measured text layout before a scene may be rendered.

    A repair is retained only when it reduces the measured issue count.  Unlike
    the old best-effort polish, an unresolved overlap is a hard gate: an
    authoritative-looking final video must not ship with unreadable text.
    """
    try:
        report = inspect_scene(code)
    except ToolError as error:
        return {"ok": False, "code": code, "report": {"ok": False, "error": str(error)}, "attempts": 0}
    if report.get("ok", False):
        return {"ok": True, "code": code, "report": report, "attempts": 0}

    attempts = 0
    current_code, current_report = code, report
    current_issues = text_layout_issue_count(report)
    while attempts < max_repairs and current_issues:
        attempts += 1
        candidate = polish_scene(client, current_code, current_report)
        candidate_code = candidate.get("code", "")
        if not candidate_code or not manim_validate_code(candidate_code)["valid"]:
            break
        try:
            candidate_report = inspect_scene(candidate_code)
        except ToolError:
            break
        candidate_issues = text_layout_issue_count(candidate_report)
        if candidate_issues >= current_issues:
            break
        current_code, current_report, current_issues = candidate_code, candidate_report, candidate_issues
        if current_report.get("ok", False):
            return {"ok": True, "code": current_code, "report": current_report, "attempts": attempts}
    return {"ok": False, "code": current_code, "report": current_report, "attempts": attempts}
