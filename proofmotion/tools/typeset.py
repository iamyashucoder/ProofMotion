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


#: Manim classes whose first string argument is compiled by a TeX engine.
TEX_CLASSES = ("MathTex", "Tex", "SingleStringMathTex")
TYPST_CLASSES = ("Typst", "TypstMath")


@tool
def typeset_scene(code: str) -> dict[str, Any]:
    """Compile every LaTeX string in a scene before anything renders.

    A scene reaches the renderer with its notation unverified, and one bad
    control sequence aborts the whole render minutes later. Compiling here costs
    milliseconds per distinct string, because Manim caches on content.

    Catches the concatenation trap in particular: adjacent string literals are
    joined by Python, so

        r"...,\\quad"
        r"K=..."

    becomes `\\quadK`, an undefined control sequence. The AST reports the joined
    value, which is exactly what the renderer will see.

    Args:
        code: The complete Manim scene source.
    """
    import ast

    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return {"ok": False, "checked": 0, "problems": [{"line": error.lineno, "error": f"SyntaxError: {error.msg}"}]}

    seen: dict[str, int] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        engine = (
            "latex" if node.func.id in TEX_CLASSES else "typst" if node.func.id in TYPST_CLASSES else None
        )
        if engine is None:
            continue
        for argument in node.args:
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                seen.setdefault(f"{engine}\x00{argument.value}", node.lineno)

    problems = []
    for key, line in seen.items():
        engine, _, expression = key.partition("\x00")
        result = typeset_check(expression, engine=engine)
        if not result["valid"]:
            problems.append({
                "line": line,
                "expression": expression[:110],
                "engine": engine,
                "error": (result.get("error") or "")[:220],
            })

    return {
        "ok": not problems,
        "checked": len(seen),
        "problems": problems,
        "advice": (
            "Fix the notation before rendering. Adjacent string literals are joined without a "
            "space, so a line ending in a control word runs into the next line's first letter."
            if problems else "Every LaTeX and Typst string in the scene compiles."
        ),
    }
