"""Components where something happens.

Every component in the library drew a state. Beats revealed the pieces of that
state one at a time, which reads as a slideshow of one picture — so a question
about a ball bouncing got a picture of a ball, and a question about whether a
series converges got a picture of some bars.

These carry `motions`: the ball falls and rebounds, the partial sums climb
toward their limit or run off the top. The distinction the viewer is being
asked to make is a distinction between two behaviours, and a behaviour is not
something a still frame has.

Each one computes its own physics and its own sums. Nothing here takes a number
on trust from whoever chose the parameters.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.regions import layout, place

AXIS_COLOR = "#9aa7bd"
ACCENT = "#4aa3df"
HIGHLIGHT = "#fbbf24"
LIMIT = "#4ade80"
DIVERGE = "#f87171"


class BouncingTrajectoryParams(BaseModel):
    """A ball dropped and rebounding to a fixed fraction of its height."""

    height: float = Field(default=8.0, gt=0, le=100, description="Drop height, in metres.")
    ratio: float = Field(
        default=0.75, gt=0, le=1.5,
        description="Rebound fraction. Above 1 the bounces grow and the total diverges.",
    )
    bounces: int = Field(default=5, ge=1, le=12, description="Bounces to draw.")
    region: str = "stage"


@component(version=1, domain="physics", params=BouncingTrajectoryParams)
def bouncing_trajectory(p: BouncingTrajectoryParams) -> Built:
    """A ball dropped and rebounding, with the ball actually falling and bouncing.

    The heights are a geometric sequence and the arcs are drawn from it, so the
    picture cannot disagree with the arithmetic underneath it.
    """
    import numpy as np
    from manim import Axes, Circle, DashedLine, MathTex, MoveAlongPath, VGroup, VMobject

    peaks = [p.height * p.ratio**i for i in range(p.bounces + 1)]
    # Time is only a horizontal axis here: each arc gets equal width, which
    # keeps late bounces visible instead of crowding them into the corner.
    span = len(peaks)
    tallest = max(peaks)

    axes = Axes(
        x_range=[0, span, 1],
        y_range=[0, tallest * 1.15, _step(tallest * 1.15)],
        x_length=8.6, y_length=4.0, tips=False,
        axis_config={"include_numbers": False, "color": AXIS_COLOR},
        y_axis_config={"include_numbers": True, "font_size": 20,
                       "decimal_number_config": {"num_decimal_places": 0 if tallest >= 10 else 1}},
    )
    ground = DashedLine(axes.c2p(0, 0), axes.c2p(span, 0), color=AXIS_COLOR, stroke_width=2)

    path = VMobject(color=ACCENT, stroke_width=4)
    points: list[Any] = []
    for index, peak in enumerate(peaks):
        # A bounce is a parabola from the ground up to its peak and back.
        start, end = index, index + 1
        for step in range(25):
            t = step / 24
            x = start + t * (end - start)
            # Falling from the peak at the left edge of the first arc, rising
            # and falling within every arc after it.
            y = peak * (1 - (2 * t - 1) ** 2) if index else peak * (1 - t) ** 2
            points.append(axes.c2p(x, max(y, 0)))
    path.set_points_smoothly(points)

    ball = Circle(radius=0.13, color=HIGHLIGHT, fill_opacity=1).move_to(points[0])

    markers = VGroup()
    for index, peak in enumerate(peaks[:4]):
        label = MathTex(f"{peak:.2f}".rstrip("0").rstrip("."), font_size=22, color=HIGHLIGHT)
        label.next_to(axes.c2p(index + (0.5 if index else 0.0), peak), np.array([0, 1, 0]), buff=0.12)
        markers.add(label)

    parts = {"axes": axes, "ground": ground, "path": path, "ball": ball, "heights": markers}
    group = VGroup(axes, ground, path, markers, ball)
    place(group, layout("title_stage_caption")[p.region])

    total = _total_distance(p.height, p.ratio, p.bounces)
    return Built(
        group=group,
        parts=parts,
        beats=[["axes", "ground"], ["path"], ["heights"], ["ball"]],
        motions=[lambda: MoveAlongPath(ball, path)],
        notes=(
            f"heights {', '.join(f'{h:.2f}' for h in peaks[:4])}...; "
            f"distance after {p.bounces} bounces {total:.2f}"
            + ("; ratio >= 1, the total grows without bound" if p.ratio >= 1 else "")
        ),
    )


def _total_distance(height: float, ratio: float, bounces: int) -> float:
    """Down once, then up and down for each bounce."""
    return height + 2 * sum(height * ratio**i for i in range(1, bounces + 1))


def _step(span: float) -> float:
    if span <= 0:
        return 1.0
    rough = span / 5
    magnitude = 10 ** math.floor(math.log10(rough))
    return next((m * magnitude for m in (1, 2, 2.5, 5, 10) if m * magnitude >= rough), magnitude * 10)


class PartialSumsParams(BaseModel):
    """Partial sums of a sequence, drawn as they accumulate."""

    terms: list[float] = Field(
        default_factory=lambda: [8.0, 6.0, 4.5, 3.375, 2.53],
        min_length=2, max_length=40,
        description="The terms being added, in order.",
    )
    limit: float | None = Field(
        default=None,
        description="The value the sums approach, drawn as a line. Omit when they diverge.",
    )
    label: str = Field(default="S_n", description="LaTeX for the partial sum.")
    region: str = "stage"


@component(version=1, domain="analysis", params=PartialSumsParams)
def partial_sums(p: PartialSumsParams) -> Built:
    """Partial sums climbing toward a limit, or running away from one.

    Convergence and divergence look identical in a table of numbers and obvious
    on a graph, which is the whole reason to draw it. The sums are computed
    here, never taken on trust.
    """
    from manim import Axes, Create, DashedLine, Dot, Line, MathTex, Succession, VGroup

    running, sums = 0.0, []
    for term in p.terms:
        running += float(term)
        sums.append(running)

    highest = max(sums + ([p.limit] if p.limit is not None else []))
    lowest = min(sums + [0.0])
    pad = (highest - lowest) * 0.15 or 1.0

    axes = Axes(
        x_range=[0, len(sums) + 1, max(1, len(sums) // 6)],
        y_range=[lowest, highest + pad, _step(highest + pad - lowest)],
        x_length=8.4, y_length=3.9, tips=False,
        axis_config={"include_numbers": True, "color": AXIS_COLOR, "font_size": 20,
                     "decimal_number_config": {"num_decimal_places": 0 if highest >= 20 else 1}},
    )

    dots, joins = VGroup(), VGroup()
    previous = None
    for index, value in enumerate(sums, start=1):
        here = axes.c2p(index, value)
        dots.add(Dot(here, radius=0.06, color=ACCENT))
        if previous is not None:
            joins.add(Line(previous, here, color=ACCENT, stroke_width=2.5))
        previous = here

    parts: dict[str, Any] = {"axes": axes, "steps": joins, "sums": dots}
    group = VGroup(axes, joins, dots)
    beats = [["axes"], ["steps", "sums"]]

    if p.limit is not None:
        line = DashedLine(axes.c2p(0, p.limit), axes.c2p(len(sums) + 1, p.limit),
                          color=LIMIT, stroke_width=3)
        tag = MathTex(f"{p.label} \\to {p.limit:g}", font_size=26, color=LIMIT)
        tag.next_to(line, direction=[0, 1, 0], buff=0.1)
        parts["limit"], parts["limit_label"] = line, tag
        group.add(line, tag)
        beats.append(["limit", "limit_label"])
    else:
        # Nothing to converge to. Saying so is the point of the picture.
        tag = MathTex(r"\text{grows without bound}", font_size=26, color=DIVERGE)
        tag.next_to(dots[-1], direction=[0, 1, 0], buff=0.15)
        parts["diverges"] = tag
        group.add(tag)
        beats.append(["diverges"])

    place(group, layout("title_stage_caption")[p.region])

    def climb() -> Any:
        """Draw the sums in order, so the trend is watched rather than seen."""
        return Succession(*[Create(segment) for segment in joins]) if len(joins) else Create(dots)

    return Built(
        group=group,
        parts=parts,
        beats=beats,
        motions=[climb],
        notes=(
            f"partial sums {', '.join(f'{s:.2f}' for s in sums[:4])}...; "
            + (f"limit {p.limit:g}" if p.limit is not None else "no limit given")
        ),
    )
