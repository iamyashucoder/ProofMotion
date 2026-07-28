"""How a piece of a figure arrives on screen.

Every beat played `FadeIn`, so everything blinked into existence at full
opacity. That is why the finished videos felt dead even after two components
learned to move: a curve that appears has no more life than a photograph of a
curve, and thirty-two of the thirty-four components only ever appeared.

Drawing is the difference. A curve traced from one end reads as a curve being
drawn; an axis that extends reads as an axis being set up; a formula written
stroke by stroke reads as someone writing it. None of that is decoration — it
is the difference between watching an explanation and being shown its result.

The choice is made from what the mobject is, so it applies to the whole library
at once rather than component by component.
"""

from __future__ import annotations

from typing import Any

#: Seconds of overlap between siblings in a group. Zero is a jump-cut of parts
#: appearing together; one is a queue. A little makes it read as one gesture.
LAG = 0.12


def _is_text(mobject: Any) -> bool:
    from proofmotion.layout.collision import is_text

    return is_text(mobject)


def _has_stroke(mobject: Any) -> bool:
    # `width or 0` raises on a numpy array — Manim stores stroke width per
    # point on some mobjects, and "the truth value of an array is ambiguous"
    # is what that reads as three frames into a render.
    try:
        import numpy as np

        width = np.asarray(mobject.get_stroke_width(), dtype=float)
        return bool(np.size(width)) and float(np.max(width)) > 0
    except Exception:  # noqa: BLE001 - not every mobject has a stroke
        return False


def _is_filled(mobject: Any) -> bool:
    try:
        import numpy as np

        value = getattr(mobject, "fill_opacity", 0.0)
        return float(np.max(np.asarray(value, dtype=float))) > 0.4 if np.size(value) else False
    except Exception:  # noqa: BLE001
        return False


def reveal(mobject: Any, run_time: float = 1.0) -> Any:
    """The animation that best introduces this mobject.

    Text is written, outlines are drawn, solid shapes grow, and a group passes
    the question to its children so a figure assembles itself piece by piece
    rather than arriving whole.
    """
    from manim import (
        AnimationGroup,
        Create,
        FadeIn,
        GrowFromCenter,
        VGroup,
        Write,
    )

    if _is_text(mobject):
        return Write(mobject, run_time=run_time)

    children = [m for m in (getattr(mobject, "submobjects", None) or []) if m is not None]
    if isinstance(mobject, VGroup) and children:
        # A group is a composition, and revealing its parts in sequence is what
        # makes a diagram look assembled rather than pasted.
        return AnimationGroup(
            *[reveal(child, run_time=run_time) for child in children],
            lag_ratio=LAG,
            run_time=run_time,
        )

    if _is_filled(mobject) and not _has_stroke(mobject):
        return GrowFromCenter(mobject, run_time=run_time)

    points = getattr(mobject, "points", None)
    if _has_stroke(mobject) and points is not None and len(points):
        return Create(mobject, run_time=run_time)

    return FadeIn(mobject, run_time=run_time)


def reveal_all(mobjects: list[Any], run_time: float = 1.0) -> Any:
    """One gesture that brings on several things at once."""
    from manim import AnimationGroup

    return AnimationGroup(
        *[reveal(m, run_time=run_time) for m in mobjects],
        lag_ratio=LAG,
        run_time=run_time,
    )
