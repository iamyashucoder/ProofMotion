"""Typesetting checks that actually compile.

Replaces tools/latex_validator.py, which counted braces and therefore passed
strings that exploded at render time. Compiling here costs milliseconds and is
cached by Manim's content-addressed tex_hash, so checking a whole proof up front
is cheap.
"""

from __future__ import annotations

from typing import Any

from proofmotion.runtime.registry import tool


@tool
def typeset_check(expression: str, engine: str = "latex") -> dict[str, Any]:
    """Verify that a math expression actually typesets, by compiling it.

    Args:
        expression: Math source. LaTeX like "\\int_a^b f(x)\\,dx", or Typst
            like "integral_a^b f(x) dif x" when engine is "typst".
        engine: "latex" (export fidelity) or "typst" (fast, no TeX install).
    """
    if engine not in {"latex", "typst"}:
        return {"expression": expression, "valid": False, "error": f"unknown engine {engine!r}; use latex or typst"}
    try:
        from manim import MathTex, TypstMath

        mobject = (MathTex if engine == "latex" else TypstMath)(expression)
    except Exception as error:  # noqa: BLE001 - TeX/Typst failures surface as many unrelated types
        message = str(error).strip().splitlines()
        return {
            "expression": expression,
            "engine": engine,
            "valid": False,
            "error": " ".join(message[-4:])[:600] or type(error).__name__,
        }
    return {
        "expression": expression,
        "engine": engine,
        "valid": True,
        "width": round(float(mobject.width), 4),
        "height": round(float(mobject.height), 4),
        "parts": len(mobject.submobjects),
    }
