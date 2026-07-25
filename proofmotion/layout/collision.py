"""Geometry shared by the layout checker and the label placer.

These two must agree. If the placer scores a position as clear and the checker
later calls it a collision, the pipeline oscillates: polish moves a label, the
gate rejects it, polish moves it back. One implementation, used by both.

"Ink" means the sampled points of every non-text vector mobject — curves, axes,
arrows, shapes. Text over ink is the defect that text-over-text checking missed,
because a formula sitting on an axis line is illegible while neither object
overlaps another piece of text.
"""

from __future__ import annotations

from typing import Any

import numpy as np

#: Ink points inside a text box before it counts as a collision. A label may
#: legitimately grave a curve at its very edge; sitting on it is the defect.
MIN_INK_POINTS = 6


def is_text(mobject: Any) -> bool:
    """True for mobjects that carry readable characters."""
    from manim import DecimalNumber, MarkupText, MathTex, SingleStringMathTex, Tex, Text

    types: tuple[type, ...] = (Text, MarkupText, MathTex, Tex, SingleStringMathTex, DecimalNumber)
    try:
        from manim import Typst, TypstMath

        types = (*types, Typst, TypstMath)
    except ImportError:
        pass
    return isinstance(mobject, types)


def text_units(mobject: Any, found: list[Any] | None = None) -> list[Any]:
    """Text-bearing mobjects anywhere in the tree, without splitting them apart.

    Descent stops at a text object: axis labels arrive inside VGroups and must be
    found, but splitting MathTex into glyphs would report every expression as
    overlapping itself.
    """
    found = [] if found is None else found
    if is_text(mobject):
        found.append(mobject)
        return found
    for child in getattr(mobject, "submobjects", ()) or ():
        text_units(child, found)
    return found


def bounds(mobject: Any) -> tuple[float, float, float, float]:
    """(left, right, bottom, top) in scene units."""
    from manim import DOWN, LEFT, RIGHT, UP

    return (
        float(mobject.get_edge_center(LEFT)[0]),
        float(mobject.get_edge_center(RIGHT)[0]),
        float(mobject.get_edge_center(DOWN)[1]),
        float(mobject.get_edge_center(UP)[1]),
    )


def ink_of(roots: list[Any]) -> list[tuple[Any, Any, np.ndarray]]:
    """Drawable, non-text geometry, tagged with the root it belongs to.

    Returns (root, member, points). The root tag is what makes "designed
    attachment" distinguishable from "collision": a tick label sits on its own
    NumberLine intentionally, so ink is only ever tested against text from a
    *different* root.

    Text glyph outlines are excluded — they are VMobjectFromSVGPath under a text
    object, and counting them turns every rendered character into ink.
    """
    collected: list[tuple[Any, Any, np.ndarray]] = []
    for root in roots:
        if is_text(root):
            continue
        glyphs = {id(part) for unit in text_units(root) for part in unit.family_members_with_points()}
        for member in root.family_members_with_points():
            if id(member) in glyphs or is_text(member):
                continue
            points = member.get_all_points()
            if len(points):
                collected.append((root, member, np.asarray(points)))
    return collected


def ink_inside(box: tuple[float, float, float, float], points: np.ndarray) -> int:
    """How many ink points fall inside a bounding box."""
    left, right, bottom, top = box
    inside = (
        (points[:, 0] >= left) & (points[:, 0] <= right) & (points[:, 1] >= bottom) & (points[:, 1] <= top)
    )
    return int(inside.sum())


def text_on_ink(
    roots: list[Any], *, min_points: int = MIN_INK_POINTS
) -> list[dict[str, Any]]:
    """Text sitting on geometry that belongs to something else.

    Args:
        roots: The scene's top-level mobjects.
        min_points: Ink points inside a text box before it counts.
    """
    ink = ink_of(roots)
    problems: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for root in roots:
        for unit in text_units(root):
            if not float(getattr(unit, "width", 0)):
                continue
            box = bounds(unit)
            for ink_root, member, points in ink:
                if ink_root is root:
                    continue  # a tick label on its own axis is design, not collision
                count = ink_inside(box, points)
                if count < min_points:
                    continue
                key = (id(unit), id(ink_root))
                if key in seen:
                    continue
                seen.add(key)
                problems.append(
                    {
                        "text": _describe(unit),
                        "over": type(ink_root).__name__,
                        "part": type(member).__name__,
                        "ink_points": count,
                    }
                )
                break
    return problems


def _describe(mobject: Any) -> str:
    text = getattr(mobject, "text", None) or getattr(mobject, "tex_string", None) or ""
    text = " ".join(str(text).split())
    return f"{type(mobject).__name__}({text[:34]})" if text else type(mobject).__name__
