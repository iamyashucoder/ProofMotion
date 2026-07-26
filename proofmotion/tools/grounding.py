"""Deterministic checks that generated visuals still answer the verified problem."""

from __future__ import annotations

import ast
import re
from typing import Any


_LAYOUT_COMMANDS = re.compile(r"\\(?:quad|qquad|;|,|!|left|right|Rightarrow|Longrightarrow|to|text)")


def _normalise_math(value: str) -> str:
    """Compare LaTeX semantically enough to ignore spacing and layout commands."""
    value = _LAYOUT_COMMANDS.sub("", value)
    value = value.replace("{", "").replace("}", "").replace(" ", "")
    return value.lower()


def _strings_in_source(code: str) -> list[str]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    return [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]


def _constructor_counts(code: str) -> dict[str, int]:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {"math": 0, "caption": 0, "play": 0}
    math_names = {"MathTex", "Tex", "TypstMath"}
    caption_names = {"Text", "Paragraph", "MarkupText"}
    math = caption = play = 0
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name):
            if node.func.id in math_names:
                math += 1
            if node.func.id in caption_names:
                caption += 1
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "self"
            and node.func.attr == "play"
        ):
            play += 1
    return {"math": math, "caption": caption, "play": play}


def final_equations(state: dict[str, Any]) -> list[str]:
    """Return the final mathematical claims the rendered answer must contain."""
    storyboard = state.get("storyboard") or {}
    scenes = storyboard.get("scenes") or []
    equations = list((scenes[-1] if scenes else {}).get("equations") or [])
    plan = state.get("math_plan") or {}
    steps = plan.get("concept_sequence") or []
    if steps and steps[-1].get("equation_latex"):
        equations.append(steps[-1]["equation_latex"])
    # Keep order, discard blank duplicates.
    return list(dict.fromkeys(e for e in equations if e and e.strip()))


def validate_scene_grounding(
    code: str,
    required_equations: list[str],
    *,
    minimum_math_objects: int = 0,
    minimum_captions: int = 0,
    minimum_play_calls: int = 0,
) -> dict[str, Any]:
    """Ensure source contains its final answer heading and verified conclusion.

    This is deliberately conservative: it does not try to prove arbitrary code
    equivalent to an equation. It stops obvious semantic drift, where a model
    emits a beautifully valid animation for a different mathematics problem.
    """
    strings = _strings_in_source(code)
    counts = _constructor_counts(code)
    normalised_source = [_normalise_math(value) for value in strings]
    has_heading = any("finalanswer" in value.replace(" ", "") for value in normalised_source)
    matched, missing = [], []
    for equation in required_equations:
        normalised = _normalise_math(equation)
        if any(normalised and normalised in source for source in normalised_source):
            matched.append(equation)
        else:
            missing.append(equation)
    detail_problems = []
    if counts["math"] < minimum_math_objects:
        detail_problems.append(f"only {counts['math']} typeset math objects; need at least {minimum_math_objects} for the explanation")
    if counts["caption"] < minimum_captions:
        detail_problems.append(f"only {counts['caption']} explanatory text objects; need at least {minimum_captions}")
    if counts["play"] < minimum_play_calls:
        detail_problems.append(f"only {counts['play']} animation beats; need at least {minimum_play_calls}")
    return {
        "valid": bool(has_heading and matched and not detail_problems),
        "has_final_answer_heading": has_heading,
        "matched_equations": matched,
        "missing_equations": missing,
        "counts": counts,
        "problems": (
            ([] if has_heading else ["missing FINAL ANSWER heading"])
            + (["none of the final verified equations appear in the scene"] if required_equations and not matched else [])
            + detail_problems
        ),
    }
