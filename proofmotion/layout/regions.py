"""Scenes declare regions, not coordinates.

Most overlap is not a near-miss to be nudged apart — it is two things claiming
the same space because nobody decided who owned it. Regions decide up front:
they tile the frame, they do not intersect, and one region holds one occupant.

That removes two whole defect classes by construction. A title cannot land on a
caption, and placing new content in a region evicts what was there, which is the
"previous section's title is still on screen underneath" bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PADDING = 0.18


@dataclass(frozen=True)
class Region:
    """A rectangle in scene units that content is fitted into."""

    name: str
    left: float
    right: float
    bottom: float
    top: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.top - self.bottom

    @property
    def center(self) -> tuple[float, float]:
        return ((self.left + self.right) / 2, (self.bottom + self.top) / 2)

    def inset(self, padding: float = PADDING) -> Region:
        return Region(
            self.name,
            self.left + padding,
            self.right - padding,
            self.bottom + padding,
            self.top - padding,
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "left": round(self.left, 3),
            "right": round(self.right, 3),
            "bottom": round(self.bottom, 3),
            "top": round(self.top, 3),
            "width": round(self.width, 3),
            "height": round(self.height, 3),
        }


def _frame() -> tuple[float, float]:
    from manim import config

    return float(config.frame_width), float(config.frame_height)


def layout(name: str = "title_stage_caption") -> dict[str, Region]:
    """Named region sets, computed from the live frame rather than hardcoded.

    Args:
        name: One of title_stage_caption, stage_sidebar, split, full.
    """
    width, height = _frame()
    left, right = -width / 2, width / 2
    bottom, top = -height / 2, height / 2
    margin = 0.3
    title_h, caption_h = 1.15, 0.95

    if name == "full":
        return {"stage": Region("stage", left + margin, right - margin, bottom + margin, top - margin)}

    title = Region("title", left + margin, right - margin, top - margin - title_h, top - margin)

    if name == "title_stage_caption":
        caption = Region("caption", left + margin, right - margin, bottom + margin, bottom + margin + caption_h)
        return {
            "title": title,
            "stage": Region("stage", left + margin, right - margin, caption.top + 0.2, title.bottom - 0.2),
            "caption": caption,
        }

    if name == "stage_sidebar":
        split_x = left + width * 0.56
        return {
            "title": title,
            "stage": Region("stage", left + margin, split_x - 0.15, bottom + margin, title.bottom - 0.2),
            "sidebar": Region("sidebar", split_x + 0.15, right - margin, bottom + margin, title.bottom - 0.2),
        }

    if name == "split":
        middle = 0.0
        return {
            "title": title,
            "left": Region("left", left + margin, middle - 0.15, bottom + margin, title.bottom - 0.2),
            "right": Region("right", middle + 0.15, right - margin, bottom + margin, title.bottom - 0.2),
        }

    raise KeyError(f"unknown layout {name!r}; available: {sorted(LAYOUT_NAMES)}")


LAYOUT_NAMES = {"title_stage_caption", "stage_sidebar", "split", "full"}


def place(mobject: Any, region: Region, *, align: str = "center", fit: bool = True, padding: float = PADDING) -> Any:
    """Scale a mobject to fit a region and position it there.

    Fitting is what stops "shrink until it fits" being the model's job — and
    stops it choosing font_size 8 to make something squeeze in, since scaling a
    laid-out group keeps the internal proportions readable.

    Args:
        mobject: What to place. Modified in place and returned.
        region: Where it goes.
        align: center, top, bottom, left, right.
        fit: Scale down when larger than the region. Never scales up.
        padding: Breathing room inside the region.
    """
    import numpy as np

    inner = region.inset(padding)
    if fit and float(mobject.width) > 0 and float(mobject.height) > 0:
        scale = min(inner.width / float(mobject.width), inner.height / float(mobject.height), 1.0)
        if scale < 1.0:
            mobject.scale(scale)

    x, y = inner.center
    mobject.move_to(np.array([x, y, 0.0]))

    if align == "top":
        mobject.shift(np.array([0.0, inner.top - float(mobject.get_top()[1]), 0.0]))
    elif align == "bottom":
        mobject.shift(np.array([0.0, inner.bottom - float(mobject.get_bottom()[1]), 0.0]))
    elif align == "left":
        mobject.shift(np.array([inner.left - float(mobject.get_left()[0]), 0.0, 0.0]))
    elif align == "right":
        mobject.shift(np.array([inner.right - float(mobject.get_right()[0]), 0.0, 0.0]))
    return mobject


def free_space(region: Region, occupied: list[tuple[float, float, float, float]], *, cells: int = 24) -> tuple[float, float] | None:
    """The centre of the largest clear patch in a region.

    Used when a label has nowhere sensible to sit next to its anchor and must be
    moved out with a leader line. A coarse grid is enough and stays fast on
    dense scenes.
    """
    inner = region.inset()
    step_x, step_y = inner.width / cells, inner.height / max(1, cells // 2)
    best, best_score = None, -1.0
    for i in range(cells):
        for j in range(max(1, cells // 2)):
            cx = inner.left + (i + 0.5) * step_x
            cy = inner.bottom + (j + 0.5) * step_y
            nearest = min(
                (
                    max(abs(cx - (l + r) / 2) - (r - l) / 2, abs(cy - (b + t) / 2) - (t - b) / 2)
                    for l, r, b, t in occupied
                ),
                default=99.0,
            )
            if nearest > best_score:
                best, best_score = (cx, cy), nearest
    return best
