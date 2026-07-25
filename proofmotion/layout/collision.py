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


#: Samples per Bézier segment. Control points alone are far too sparse for
#: straight geometry: an axis is one cubic with four control points, so a formula
#: sitting directly on the axis line contained almost none of them and was
#: reported clean while the rendered frame showed the collision plainly.
SEGMENT_SAMPLES = 12


def densify(points: np.ndarray) -> np.ndarray:
    """Sample along each cubic Bézier segment instead of trusting control points."""
    if len(points) < 4:
        return points
    usable = len(points) - (len(points) % 4)
    if usable < 4:
        return points
    control = points[:usable].reshape(-1, 4, points.shape[1])
    t = np.linspace(0.0, 1.0, SEGMENT_SAMPLES).reshape(1, -1, 1)
    p0, p1, p2, p3 = (control[:, i, :][:, None, :] for i in range(4))
    curve = (
        (1 - t) ** 3 * p0
        + 3 * (1 - t) ** 2 * t * p1
        + 3 * (1 - t) * t**2 * p2
        + t**3 * p3
    )
    return curve.reshape(-1, points.shape[1])


def _is_axis(mobject: Any) -> bool:
    from manim import CoordinateSystem, NumberLine

    return isinstance(mobject, (NumberLine, CoordinateSystem))


def axis_owned_text(roots: list[Any]) -> dict[int, set[int]]:
    """Map each text to the axes that own it, i.e. its tick and axis labels.

    Only this relationship is exempt from collision. An earlier rule exempted
    anything sharing a root, which a scene defeated simply by putting the whole
    figure in one VGroup — the axes and a stray label then counted as the same
    tree, and a label sitting on the axis line was reported clean.
    """
    owners: dict[int, set[int]] = {}

    def walk(node: Any, axes: tuple[int, ...]) -> None:
        if is_text(node):
            if axes:
                owners.setdefault(id(node), set()).update(axes)
            return
        inner = (*axes, id(node)) if _is_axis(node) else axes
        for child in getattr(node, "submobjects", ()) or ():
            walk(child, inner)

    for root in roots:
        walk(root, ())
    return owners


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

    def walk(node: Any, axes: tuple[int, ...], glyphs: set[int]) -> None:
        if is_text(node) or id(node) in glyphs:
            return
        inner = (*axes, id(node)) if _is_axis(node) else axes
        # A node's own points, not get_all_points(): the family version rolls every
        # descendant into the container, so a VGroup wrapping the figure became one
        # giant blob owned by nothing, and its own axis's tick labels collided with it.
        points = getattr(node, "points", None)
        points = points if points is not None and len(points) else []
        if len(points):
            collected.append(((inner[-1] if inner else id(node)), node, densify(np.asarray(points))))
        for child in getattr(node, "submobjects", ()) or ():
            walk(child, inner, glyphs)

    for root in roots:
        if is_text(root):
            continue
        glyphs = {id(part) for unit in text_units(root) for part in unit.family_members_with_points()}
        glyphs |= {id(unit) for unit in text_units(root)}
        walk(root, (), glyphs)
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
    owners = axis_owned_text(roots)
    problems: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for root in roots:
        for unit in text_units(root):
            if not float(getattr(unit, "width", 0)):
                continue
            box = bounds(unit)
            owned_by = owners.get(id(unit), set())
            for owner_id, member, points in ink:
                if owner_id in owned_by:
                    continue  # a tick label on its own axis is design, not collision
                count = ink_inside(box, points)
                if count < min_points:
                    continue
                key = (id(unit), owner_id)
                if key in seen:
                    continue
                seen.add(key)
                # An axis tick number that a curve happens to cross is a minor
                # legibility issue that even hand-made plots have, and the axis
                # owns its own numbering so nothing can move them. A label, title
                # or formula sitting on geometry is the defect worth failing on.
                severity = "minor" if owned_by else "major"
                problems.append(
                    {
                        "text": _describe(unit),
                        "over": type(member).__name__,
                        "part": type(member).__name__,
                        "ink_points": count,
                        "severity": severity,
                    }
                )
                break
    return problems


def major_collisions(roots: list[Any], **kwargs: Any) -> list[dict[str, Any]]:
    """Only the collisions worth failing a build over."""
    return [hit for hit in text_on_ink(roots, **kwargs) if hit["severity"] == "major"]


def _describe(mobject: Any) -> str:
    text = getattr(mobject, "text", None) or getattr(mobject, "tex_string", None) or ""
    text = " ".join(str(text).split())
    return f"{type(mobject).__name__}({text[:34]})" if text else type(mobject).__name__
