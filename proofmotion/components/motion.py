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
from itertools import pairwise
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


class NeuralNetworkParams(BaseModel):
    """A feedforward network, with data flowing through it."""

    layers: list[int] = Field(
        default_factory=lambda: [3, 5, 5, 2],
        min_length=2, max_length=6,
        description="Units per layer, input first, e.g. [3, 5, 5, 2].",
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Optional name under each layer, e.g. ['x', 'hidden', 'hidden', 'y'].",
    )
    highlight: str = Field(default="", description="LaTeX for the value entering, e.g. 'x'.")
    region: str = "stage"


@component(version=1, domain="machine_learning", params=NeuralNetworkParams)
def neural_network(p: NeuralNetworkParams) -> Built:
    """A feedforward network with activation flowing from input to output.

    The flow is the point. A diagram of circles and lines says what a network
    is made of; watching a value enter on the left and arrive on the right is
    what the layers are actually doing.
    """
    import numpy as np
    from manim import Circle, Dot, Line, MathTex, Succession, Text, VGroup

    width, height = 8.0, 3.6
    tallest = max(p.layers)
    gap_x = width / max(1, len(p.layers) - 1)
    radius = min(0.24, height / (tallest * 3.2))

    columns: list[list[Any]] = []
    nodes = VGroup()
    for index, count in enumerate(p.layers):
        column = []
        x = -width / 2 + index * gap_x
        spread = height / max(1, count)
        for unit in range(count):
            y = (unit - (count - 1) / 2) * spread
            circle = Circle(radius=radius, color=ACCENT, fill_opacity=0.25, stroke_width=2)
            circle.move_to(np.array([x, y, 0.0]))
            column.append(circle)
            nodes.add(circle)
        columns.append(column)

    edges = VGroup()
    for left, right in pairwise(columns):
        for source in left:
            for target in right:
                edges.add(Line(
                    source.get_center(), target.get_center(),
                    stroke_width=1.1, color="#3a4a5e",
                ))

    captions = VGroup()
    for index, name in enumerate(p.labels[: len(p.layers)]):
        if not name:
            continue
        text = Text(name, font_size=20, color=AXIS_COLOR)
        text.next_to(columns[index][-1], np.array([0, 1, 0]), buff=0.22)
        captions.add(text)

    parts: dict[str, Any] = {"edges": edges, "units": nodes}
    group = VGroup(edges, nodes, captions)
    if len(captions):
        parts["layer_labels"] = captions

    entering = None
    if p.highlight:
        entering = MathTex(p.highlight, font_size=28, color=HIGHLIGHT)
        entering.next_to(columns[0][len(columns[0]) // 2], np.array([-1, 0, 0]), buff=0.3)
        parts["input"] = entering
        group.add(entering)

    place(group, layout("title_stage_caption")[p.region])

    def flow() -> Any:
        """One pulse per layer, so the value is watched crossing the network."""
        from manim import AnimationGroup, FadeOut, MoveAlongPath

        stages: list[Any] = []
        for left, right in pairwise(columns):
            pulses, paths = VGroup(), []
            for position, source in enumerate(left):
                # Fanned across the next layer rather than funnelled into its
                # middle. Every pulse converging on one node reads as a
                # bottleneck, which is the opposite of what a dense layer does.
                share = position / max(1, len(left) - 1)
                target = right[round(share * (len(right) - 1))]
                pulses.add(Dot(source.get_center(), radius=0.055, color=HIGHLIGHT))
                paths.append(Line(source.get_center(), target.get_center()))
            stages.append(AnimationGroup(*[
                MoveAlongPath(dot, path) for dot, path in zip(pulses, paths, strict=False)
            ]))
            stages.append(FadeOut(pulses, run_time=0.12))
        return Succession(*stages) if stages else FadeOut(nodes, run_time=0.1)

    return Built(
        group=group, parts=parts,
        beats=[["edges"], ["units"]] + ([["layer_labels"]] if len(captions) else [])
        + ([["input"]] if entering is not None else []),
        motions=[flow],
        notes=f"layers {p.layers}; {sum(a * b for a, b in zip(p.layers, p.layers[1:], strict=False))} weights",
    )
