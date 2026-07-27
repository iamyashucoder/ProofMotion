"""Expose the chapter-expert registry to planning agents."""

from typing import Literal

from proofmotion.knowledge.jee_cases import CHAPTER_CASES, execute_case
from proofmotion.knowledge.jee_experts import CHAPTERS, coverage
from proofmotion.runtime.registry import ToolError, tool


@tool
def jee_chapter_expert(chapter: str) -> dict:
    """Return the mandatory solver, verification, visual, and test gate for one JEE chapter."""
    key = chapter.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in CHAPTERS:
        raise ToolError(f"Unknown JEE chapter {chapter!r}. Use jee_chapter_coverage to inspect available chapter IDs.")
    return CHAPTERS[key]


@tool
def jee_chapter_coverage(subject: Literal["all", "physics", "chemistry", "mathematics"] = "all") -> dict:
    """Audit complete JEE chapter coverage and expose remaining expert gaps."""
    report = coverage()
    if subject == "all":
        return report
    chapters = {key: value for key, value in CHAPTERS.items() if value["subject"] == subject}
    return {"subject": subject, "total": len(chapters), "chapters": chapters}


@tool
def jee_chapter_case(chapter: str, execute: bool = False) -> dict:
    """Return, or execute, a chapter's deterministic representative known-answer case."""
    key = chapter.strip().lower().replace(" ", "_").replace("-", "_")
    if key not in CHAPTER_CASES:
        raise ToolError(f"Unknown JEE chapter {chapter!r}.")
    return execute_case(key) if execute else CHAPTER_CASES[key]
