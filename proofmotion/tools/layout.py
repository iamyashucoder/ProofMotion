"""Spatial reasoning tools.

Manim has no layout engine — only next_to and arrange. That gap is why every
model tested, including a hand-written scene, produced overlapping labels.
Prompt rules cannot fix a missing subsystem; measurement can.
"""

from __future__ import annotations

import functools
from typing import Any

from proofmotion.runtime.registry import ToolError, tool


@functools.lru_cache(maxsize=1)
def _frame() -> tuple[float, float]:
    from manim import config

    return float(config.frame_width), float(config.frame_height)


@tool
def layout_frame() -> dict[str, Any]:
    """Return the usable frame in Manim scene units.

    Objects must stay inside these bounds. Use the safe_* values, which keep a
    margin, rather than placing objects flush against the edge.
    """
    width, height = _frame()
    margin = 0.3
    return {
        "width": width,
        "height": height,
        "left": -width / 2,
        "right": width / 2,
        "bottom": -height / 2,
        "top": height / 2,
        "safe_left": -width / 2 + margin,
        "safe_right": width / 2 - margin,
        "safe_bottom": -height / 2 + margin,
        "safe_top": height / 2 - margin,
        "margin": margin,
    }


@tool
def layout_measure(kind: str, content: str, font_size: int = 48) -> dict[str, Any]:
    """Measure how much space a text or math object will occupy, before placing it.

    Args:
        kind: One of "Text", "MathTex", "Tex", "TypstMath".
        content: The string to measure.
        font_size: Font size the object will use.
    """
    import manim

    if kind not in {"Text", "MathTex", "Tex", "TypstMath"}:
        raise ToolError(f"kind must be Text, MathTex, Tex, or TypstMath; got {kind!r}")
    try:
        mobject = getattr(manim, kind)(content, font_size=font_size)
    except Exception as error:
        raise ToolError(f"{kind}({content!r}) failed to build: {str(error)[:300]}") from error
    frame_width, frame_height = _frame()
    return {
        "kind": kind,
        "content": content,
        "width": round(float(mobject.width), 4),
        "height": round(float(mobject.height), 4),
        "fits_in_frame": bool(mobject.width < frame_width - 0.6 and mobject.height < frame_height - 0.6),
        "suggested_scale": round(min(1.0, (frame_width - 0.6) / float(mobject.width)), 3) if mobject.width else 1.0,
    }


@tool
def layout_check(boxes: list[dict]) -> dict[str, Any]:
    """Check planned object placements for overlaps and frame escapes.

    Call this before writing positioning code. Each box is
    {"name": str, "x": float, "y": float, "width": float, "height": float},
    where x and y are the object's centre in scene units.

    Args:
        boxes: The planned placements to check.
    """
    frame = layout_frame()
    parsed = []
    for i, box in enumerate(boxes):
        missing = {"name", "x", "y", "width", "height"} - set(box)
        if missing:
            raise ToolError(f"box {i} is missing {sorted(missing)}")
        parsed.append(
            {
                "name": str(box["name"]),
                "left": float(box["x"]) - float(box["width"]) / 2,
                "right": float(box["x"]) + float(box["width"]) / 2,
                "bottom": float(box["y"]) - float(box["height"]) / 2,
                "top": float(box["y"]) + float(box["height"]) / 2,
            }
        )

    overlaps = []
    for i, a in enumerate(parsed):
        for b in parsed[i + 1 :]:
            dx = min(a["right"], b["right"]) - max(a["left"], b["left"])
            dy = min(a["top"], b["top"]) - max(a["bottom"], b["bottom"])
            if dx > 0 and dy > 0:
                overlaps.append(
                    {"between": [a["name"], b["name"]], "overlap_width": round(dx, 3), "overlap_height": round(dy, 3)}
                )

    escapes = [
        {
            "name": box["name"],
            "sides": [
                side
                for side, bad in (
                    ("left", box["left"] < frame["safe_left"]),
                    ("right", box["right"] > frame["safe_right"]),
                    ("bottom", box["bottom"] < frame["safe_bottom"]),
                    ("top", box["top"] > frame["safe_top"]),
                )
                if bad
            ],
        }
        for box in parsed
    ]
    escapes = [e for e in escapes if e["sides"]]

    return {
        "ok": not overlaps and not escapes,
        "overlaps": overlaps,
        "out_of_frame": escapes,
        "advice": "Move overlapping objects to separate rows, or scale them down."
        if overlaps or escapes
        else "Layout is clear.",
    }
