"""Restricted tools exposing the local, source-attributed answer registry."""

from __future__ import annotations

from typing import Any

from proofmotion.knowledge.answer_oracle import audit_final_answer, lookup_reference_answer
from proofmotion.runtime.registry import tool


@tool
def reference_answer_lookup(prompt: str) -> dict[str, Any]:
    """Look up an exact vetted reference answer for a complete problem statement.

    The registry is local and source-attributed.  It returns no result rather
    than matching an approximate or merely similar question.
    """
    return lookup_reference_answer(prompt)


@tool
def reference_answer_audit(prompt: str, candidate_latex: str) -> dict[str, Any]:
    """Compare a derived final answer with an exact vetted reference, if one exists."""
    return audit_final_answer(prompt, candidate_latex)
