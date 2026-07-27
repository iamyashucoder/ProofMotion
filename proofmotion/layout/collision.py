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

#: Clearance demanded around text, in scene units. Strict overlap was too
#: forgiving: a label pressed right against a curve or an axis number reads as
#: badly as one on top of it, and measured as clean. Text needs breathing room,
#: not merely disjoint bounding boxes.
CLEARANCE = 0.07


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


#: Grid spacing for the inside of a filled shape, in scene units. Small enough
#: that a short label lying on a fill contains at least MIN_INK_POINTS of them.
FILL_SAMPLE_STEP = 0.09

#: Ceiling on interior samples per shape, so a large fill cannot dominate.
MAX_FILL_SAMPLES = 6000

#: A fill with less opacity than this is a wash the text still reads through.
MIN_FILL_OPACITY = 0.12


def _is_axis(mobject: Any) -> bool:
    from manim import CoordinateSystem, NumberLine

    return isinstance(mobject, (NumberLine, CoordinateSystem))


#: Set on a shape a component deliberately puts text inside — an array cell, a
#: badge, a labelled box. See holds_text().
HOLDS_TEXT = "pm_holds_text"


def holds_text(mobject: Any) -> Any:
    """Mark a shape as a container for the text placed in it, and return it.

    Geometry cannot tell a container from an accident. An array cell holding
    its value and a label lying across a filled disc are the same picture to a
    measuring tool: text inside a fill, and — measured — at the same size ratio,
    25.1 against 24.2. One is designed and tested, the other is the defect this
    checker exists to catch.

    So the component says which it is. This is deliberately something only a
    component author writes: raw scene code does not set it, so a hand-placed
    label on a figure is still reported.
    """
    setattr(mobject, HOLDS_TEXT, True)
    return mobject


def _is_backdrop(mobject: Any) -> bool:
    """Shapes whose whole job is to sit behind or around text.

    BackgroundRectangle and SurroundingRectangle exist to be drawn under or
    around a label. Counting them as ink reported every boxed label as a major
    collision — their border hugs the text, so even the outline alone landed
    inside the clearance box.
    """
    if getattr(mobject, HOLDS_TEXT, False):
        return True
    try:
        from manim import BackgroundRectangle, SurroundingRectangle
    except ImportError:  # pragma: no cover - both ship with manim
        return False
    return isinstance(mobject, (BackgroundRectangle, SurroundingRectangle))


def _fill_opacity(mobject: Any) -> float:
    """How solidly a mobject is filled, as a single number."""
    value = getattr(mobject, "fill_opacity", 0.0)
    try:
        # Manim stores this per-point on some mobjects.
        return float(np.max(np.asarray(value, dtype=float))) if np.size(value) else 0.0
    except (TypeError, ValueError):
        return 0.0


def _subpaths(mobject: Any, points: np.ndarray) -> list[np.ndarray]:
    """Closed outlines making up a shape.

    Treating every point as one polygon joins the end of one subpath to the
    start of the next, and a ring or a letter-shaped hole then tests as solid.
    """
    try:
        paths = [np.asarray(p) for p in mobject.get_subpaths()]
    except Exception:  # noqa: BLE001 - not every mobject exposes subpaths
        paths = []
    paths = [p for p in paths if len(p) >= 4]
    return [densify(p) for p in paths] if paths else [points]


def _inside_polygon(grid: np.ndarray, polygon: np.ndarray) -> np.ndarray:
    """Even-odd ray cast: which grid points lie within the outline."""
    x, y = grid[:, 0], grid[:, 1]
    x1, y1 = polygon[:, 0], polygon[:, 1]
    x2, y2 = np.roll(x1, -1), np.roll(y1, -1)

    straddles = (y1[:, None] > y[None, :]) != (y2[:, None] > y[None, :])
    dy = (y2 - y1)[:, None]
    # Horizontal edges never straddle, so the division they guard is masked out.
    safe = np.where(dy == 0, 1.0, dy)
    crossing_x = (x2 - x1)[:, None] * (y[None, :] - y1[:, None]) / safe + x1[:, None]
    return np.logical_xor.reduce(straddles & (x[None, :] < crossing_x), axis=0)


def fill_points(mobject: Any, boundary: np.ndarray) -> np.ndarray:
    """Sample the interior of a filled shape, so its inside counts as ink.

    Outline points alone are not the shape. A filled disc has no points
    anywhere but its rim, so a label lying across the middle of one contained
    no ink at all and measured perfectly clean — which is how "frictionless
    axle" came to sit unreadable across a disc while the checker reported zero
    overlaps.
    """
    if _fill_opacity(mobject) < MIN_FILL_OPACITY or _is_backdrop(mobject):
        return np.empty((0, boundary.shape[1]))

    left, right = float(np.min(boundary[:, 0])), float(np.max(boundary[:, 0]))
    bottom, top = float(np.min(boundary[:, 1])), float(np.max(boundary[:, 1]))
    width, height = right - left, top - bottom
    if width <= 0 or height <= 0:
        return np.empty((0, boundary.shape[1]))

    # Coarsen rather than refuse, so a large fill still registers.
    step = max(FILL_SAMPLE_STEP, np.sqrt(width * height / MAX_FILL_SAMPLES))
    xs = np.arange(left + step / 2, right, step)
    ys = np.arange(bottom + step / 2, top, step)
    if not len(xs) or not len(ys):
        return np.empty((0, boundary.shape[1]))
    mesh = np.stack(np.meshgrid(xs, ys), axis=-1).reshape(-1, 2)

    inside = np.zeros(len(mesh), dtype=bool)
    for path in _subpaths(mobject, boundary):
        if len(path) >= 3:
            inside ^= _inside_polygon(mesh, path[:, :2])
    kept = mesh[inside]
    if not len(kept):
        return np.empty((0, boundary.shape[1]))
    return np.column_stack([kept, np.zeros((len(kept), boundary.shape[1] - 2))])


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
        if _is_backdrop(node):
            # A backdrop is not ink in any part. Its border hugs the text it
            # wraps, so even the outline alone landed inside the clearance box
            # and reported every boxed label as a major collision.
            return
        inner = (*axes, id(node)) if _is_axis(node) else axes
        # A node's own points, not get_all_points(): the family version rolls every
        # descendant into the container, so a VGroup wrapping the figure became one
        # giant blob owned by nothing, and its own axis's tick labels collided with it.
        points = getattr(node, "points", None)
        points = points if points is not None and len(points) else []
        if len(points):
            outline = densify(np.asarray(points))
            # The inside of a filled shape is ink too. Without this a label
            # lying across a filled disc contained no points at all, because
            # they are all out on the rim, and measured perfectly clean.
            interior = fill_points(node, outline)
            ink = np.vstack([outline, interior]) if len(interior) else outline
            collected.append(((inner[-1] if inner else id(node)), node, ink))
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
    roots: list[Any], *, min_points: int = MIN_INK_POINTS, clearance: float = CLEARANCE
) -> list[dict[str, Any]]:
    """Text sitting on, or pressed against, geometry that belongs to something else.

    Args:
        roots: The scene's top-level mobjects.
        min_points: Ink points inside a text box before it counts.
        clearance: Breathing room demanded around the text.
    """
    ink = ink_of(roots)
    owners = axis_owned_text(roots)
    problems: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()

    for root in roots:
        for unit in text_units(root):
            if not float(getattr(unit, "width", 0)):
                continue
            left, right, bottom, top = bounds(unit)
            box = (left - clearance, right + clearance, bottom - clearance, top + clearance)
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
