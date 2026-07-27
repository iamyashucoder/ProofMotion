"""Vetted reference-answer checks for complete worked problems.

This module is deliberately conservative.  It never searches the public web or
guesses that two similarly worded questions are the same question.  A reference
is used only when every distinguishing phrase in a curated record occurs in the
prompt.  That makes the layer safe to run alongside the normal solver: an
unknown problem simply receives independent mathematical checks as before.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReferenceAnswer:
    """A source-attributed answer for one precisely identified problem."""

    id: str
    match_terms: tuple[str, ...]
    answer_latex: str
    source: str
    source_kind: str
    derivation_note: str


# Records enter this list only with a source and an independently reproducible
# derivation.  It is intentionally small at first: a wrong broad match is worse
# than no reference match.  More official answer keys can be added as curated,
# versioned records without changing the pipeline.
REFERENCE_ANSWERS: tuple[ReferenceAnswer, ...] = (
    ReferenceAnswer(
        id="meter_scale_alternating_friction",
        match_terms=(
            "uniform meter scale",
            "left one at 0.00 cm",
            "right one at 90.00 cm",
            "0.40",
            "0.32",
        ),
        answer_latex=r"x_R = 25.60\,\mathrm{cm}",
        source="Problem statement and expected result supplied by the project user; independently reproduced by alternating static/dynamic-friction force balance.",
        source_kind="user_verified",
        derivation_note="At the two switches, equate kinetic friction on the sliding finger to limiting static friction on the other finger.",
    ),
)


def _normalise_text(value: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9.]+", " ", value.lower()).split())


def _normalise_answer(value: str) -> str:
    """Remove display-only LaTex while retaining variables, units, and values."""
    text = value.lower()
    text = re.sub(r"\\boxed\{(.+)\}", r"\1", text)
    text = text.replace(r"\,", "").replace(r"\!", "")
    text = re.sub(r"\\(?:mathrm|text)\{([^}]*)\}", r"\1", text)
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", "", text)


def _numeric_values(value: str) -> list[float]:
    return [float(number) for number in re.findall(r"(?<![a-z])[-+]?\d+(?:\.\d+)?", value.lower())]


def lookup_reference_answer(prompt: str) -> dict[str, Any]:
    """Find one exact curated reference record, if the prompt identifies it."""
    normalized = _normalise_text(prompt)
    for record in REFERENCE_ANSWERS:
        if all(_normalise_text(term) in normalized for term in record.match_terms):
            return {"available": True, "reference": asdict(record)}
    return {
        "available": False,
        "reference": None,
        "reason": "No exact vetted reference record matches this prompt; retain independent mathematical verification.",
    }


def audit_final_answer(prompt: str, candidate_latex: str | None) -> dict[str, Any]:
    """Compare a final answer with a vetted answer without making a guess.

    Exact normalised LaTex is preferred.  Numeric comparison accepts harmless
    formatting differences (``25.6`` vs ``25.60``), but only after a reference
    record was identified by the full problem wording.
    """
    lookup = lookup_reference_answer(prompt)
    if not lookup["available"]:
        return {"status": "no_reference", "matched": None, **lookup}
    if not candidate_latex or not candidate_latex.strip():
        return {
            "status": "missing_candidate",
            "matched": False,
            "candidate_latex": candidate_latex or "",
            **lookup,
        }

    reference = lookup["reference"]
    expected = reference["answer_latex"]
    exact = _normalise_answer(candidate_latex) == _normalise_answer(expected)
    candidate_numbers, expected_numbers = _numeric_values(candidate_latex), _numeric_values(expected)
    numeric_match = bool(candidate_numbers and expected_numbers) and len(candidate_numbers) == len(expected_numbers) and all(
        abs(left - right) <= 1e-9 for left, right in zip(candidate_numbers, expected_numbers)
    )
    matched = exact or numeric_match
    return {
        "status": "matched" if matched else "mismatch",
        "matched": matched,
        "comparison": "exact_latex" if exact else "numeric_value" if numeric_match else "different_result",
        "candidate_latex": candidate_latex,
        "expected_latex": expected,
        **lookup,
    }
