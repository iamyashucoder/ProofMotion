"""Automatic label placement.

Regions solve the coarse problem. They cannot solve labels that must attach to a
specific point — the value at a maximum, the angle at a vertex, the name of a
curve. Those have to sit near their anchor, and near the anchor is exactly where
the curve is.

This is the map-labelling problem, and the standard answer is to score candidate
positions rather than pick one and hope. Candidates are the eight compass
directions at a few distances; each is scored against ink, against labels already
placed, and against the frame. When everything collides, the label moves to open
space with a leader line — which is what a careful figure does by hand and what
Manim will never do on its own.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from proofmotion.layout.collision import bounds, ink_inside, ink_of

#: Eight compass directions, clockwise from east.
DIRECTIONS: tuple[tuple[float, float], ...] = (
    (1.0, 0.0), (0.7071, 0.7071), (0.0, 1.0), (-0.7071, 0.7071),
    (-1.0, 0.0), (-0.7071, -0.7071), (0.0, -1.0), (0.7071, -0.7071),
)
DISTANCES: tuple[float, ...] = (0.28, 0.5, 0.8, 1.2)

INK_PENALTY = 12.0
LABEL_PENALTY = 30.0
FRAME_PENALTY = 100.0
DISTANCE_PENALTY = 1.4


def _box_at(label: Any, x: float, y: float) -> tuple[float, float, float, float]:
    half_w, half_h = float(label.width) / 2, float(label.height) / 2
    return (x - half_w, x + half_w, y - half_h, y + half_h)


def _overlap_area(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> float:
    dx = min(a[1], b[1]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[2], b[2])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def score_position(
    box: tuple[float, float, float, float],
    ink: list[tuple[Any, Any, np.ndarray]],
    placed: list[tuple[float, float, float, float]],
    frame: tuple[float, float],
    distance: float,
) -> float:
    """Lower is better. Ink is bad, other labels are worse, leaving frame is fatal."""
    score = distance * DISTANCE_PENALTY
    for _root, _member, points in ink:
        hits = ink_inside(box, points)
        if hits:
            score += INK_PENALTY * math.log1p(hits)
    for other in placed:
        score += LABEL_PENALTY * _overlap_area(box, other)
    half_w, half_h = frame[0] / 2 - 0.2, frame[1] / 2 - 0.2
    if box[0] < -half_w or box[1] > half_w or box[2] < -half_h or box[3] > half_h:
        score += FRAME_PENALTY
    return score


def place_label(
    label: Any,
    anchor: Any,
    *,
    avoid: list[Any] | None = None,
    placed: list[Any] | None = None,
    leader_threshold: float = INK_PENALTY,
) -> dict[str, Any]:
    """Position `label` near `anchor` where it collides least.

    Args:
        label: The mobject to position. Moved in place.
        anchor: A point (x, y) or a mobject whose centre is the anchor.
        avoid: Mobjects whose geometry the label should not sit on.
        placed: Labels already positioned, which this one must not cover.
        leader_threshold: Above this score every candidate is compromised, so the
            label is moved to open space and a leader line is returned.

    Returns:
        {"placed": label, "leader": Line | None, "score": float, "direction": str}
    """
    from manim import Line, config

    point = np.asarray(anchor.get_center() if hasattr(anchor, "get_center") else (*anchor, 0.0), dtype=float)
    ink = ink_of(list(avoid or []))
    taken = [bounds(p) for p in (placed or [])]
    frame = (float(config.frame_width), float(config.frame_height))

    names = ("E", "NE", "N", "NW", "W", "SW", "S", "SE")
    best: tuple[float, tuple[float, float], str] | None = None
    for distance in DISTANCES:
        for (dx, dy), name in zip(DIRECTIONS, names, strict=False):
            cx = float(point[0]) + dx * (distance + float(label.width) / 2)
            cy = float(point[1]) + dy * (distance + float(label.height) / 2)
            value = score_position(_box_at(label, cx, cy), ink, taken, frame, distance)
            if best is None or value < best[0]:
                best = (value, (cx, cy), name)

    assert best is not None
    score, (cx, cy), direction = best
    label.move_to(np.array([cx, cy, 0.0]))

    if score <= leader_threshold:
        return {"placed": label, "leader": None, "score": round(score, 2), "direction": direction}

    # Everything near the anchor is occupied. Move out and connect.
    spot = _open_spot(label, ink, taken, frame)
    if spot is None:
        return {"placed": label, "leader": None, "score": round(score, 2), "direction": direction}
    label.move_to(np.array([spot[0], spot[1], 0.0]))
    leader = Line(point, label.get_edge_center(_toward(point, spot)), stroke_width=1.6, stroke_opacity=0.55)
    return {"placed": label, "leader": leader, "score": round(score, 2), "direction": "leader"}


def _toward(point: np.ndarray, spot: tuple[float, float]) -> Any:
    from manim import DOWN, LEFT, RIGHT, UP

    dx, dy = spot[0] - float(point[0]), spot[1] - float(point[1])
    if abs(dx) > abs(dy):
        return LEFT if dx > 0 else RIGHT
    return DOWN if dy > 0 else UP


def _open_spot(
    label: Any,
    ink: list[tuple[Any, Any, np.ndarray]],
    taken: list[tuple[float, float, float, float]],
    frame: tuple[float, float],
    *, cells: int = 16,
) -> tuple[float, float] | None:
    """Least-occupied position anywhere in frame, on a coarse grid."""
    half_w, half_h = frame[0] / 2 - 0.4, frame[1] / 2 - 0.4
    best, best_score = None, None
    for i in range(cells):
        for j in range(cells // 2):
            cx = -half_w + (i + 0.5) * (2 * half_w / cells)
            cy = -half_h + (j + 0.5) * (2 * half_h / (cells // 2))
            value = score_position(_box_at(label, cx, cy), ink, taken, frame, 0.0)
            if best_score is None or value < best_score:
                best, best_score = (cx, cy), value
    return best
