"""Shapes of ideas, not subjects.

Fifty-four subject components exist and nine have ever been used; the gap was
never coverage, it was that a question with no matching subject had nowhere to
go. These components draw a *class* of idea from labels alone: a comparison, a
tree, a stack, a grid. Together with flow_diagram they are the whole shape
library, and the guard is deliberate: five shapes at most, each covering a
class of idea rather than a topic. A sixth shape is a design decision, not an
addition.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from proofmotion.components.base import Built, component
from proofmotion.layout.collision import holds_text
from proofmotion.layout.regions import layout, place
from proofmotion.components.palette import PALETTE


#: Everything here lays out into the same horizontal budget flow_diagram uses.
STAGE_W = 9.2
STAGE_H = 4.5


def _fit(label: Any, width: float, height: float) -> Any:
    """Shrink-only fit of a label into a box's inner area."""
    label.scale_to_fit_width(min(label.width, width * 0.86))
    if float(label.height) > height * 0.72:
        label.scale(height * 0.72 / float(label.height))
    return label


class ComparisonParams(BaseModel):
    """Two columns of aligned rows: this versus that."""

    left_title: str = Field(
        min_length=1, description="Left column heading, e.g. 'SFT'.",
    )
    right_title: str = Field(
        min_length=1, description="Right column heading, e.g. 'RLHF'.",
    )
    rows: list[list[str]] = Field(
        min_length=1, max_length=8,
        description=(
            "Each row as [left cell, right cell], e.g. "
            "[['labelled demonstrations', 'preference pairs'], ['one pass', 'reward model + PPO']]. "
            "An empty string leaves that side of the row blank."
        ),
    )
    row_labels: list[str] = Field(
        default_factory=list,
        description="Optional label per row down the left, e.g. ['data', 'cost']. Empty means no label column.",
    )
    highlight: list[int] = Field(
        default_factory=list,
        description="Row indices to accent, e.g. [0, 2]. Empty accents nothing.",
    )
    region: str = "stage"

    @field_validator("rows")
    @classmethod
    def _rows_are_pairs(cls, rows: list[list[str]]) -> list[list[str]]:
        for index, row in enumerate(rows, start=1):
            if len(row) != 2:
                raise ValueError(
                    f"row {index} has {len(row)} cells; every comparison row needs exactly two cells, a left and a right."
                )
        return rows

    @model_validator(mode="after")
    def _consistent(self) -> ComparisonParams:
        if self.row_labels and len(self.row_labels) != len(self.rows):
            raise ValueError(
                f"there are {len(self.row_labels)} row labels for {len(self.rows)} rows; give one label per row or none."
            )
        for index in self.highlight:
            if not 0 <= index < len(self.rows):
                raise ValueError(
                    f"highlight index {index} is out of range for {len(self.rows)} rows."
                )
        return self


@component(version=1, domain="general", params=ComparisonParams, shape="comparison")
def comparison(p: ComparisonParams) -> Built:
    """Two things side by side, row by row — this versus that, before and after, trade-offs.

    The reveal is the argument: each beat lands one aligned pair, so the
    audience reads a difference at a time instead of a finished table.
    """
    import numpy as np
    from manim import Line, RoundedRectangle, Text, VGroup

    count = len(p.rows)
    header_h = 0.62
    row_h = min(0.6, (STAGE_H - header_h - 0.18 - 0.12 * (count - 1)) / count)
    label_w = 1.7 if p.row_labels else 0.0
    label_gap = 0.25 if p.row_labels else 0.0
    col_w = min(4.2, (STAGE_W - label_w - label_gap - 0.3) / 2)

    total_w = label_w + label_gap + 2 * col_w + 0.3
    total_h = header_h + 0.18 + count * row_h + (count - 1) * 0.12
    x_left = -total_w / 2 + label_w + label_gap + col_w / 2
    x_right = x_left + col_w + 0.3
    x_label = -total_w / 2 + label_w / 2

    def cell(text: str, width: float, height: float, x: float, y: float, *, accent: bool) -> VGroup:
        empty = not text
        box = RoundedRectangle(
            width=width, height=height, corner_radius=0.1,
            color=PALETTE.muted if empty else (PALETTE.highlight if accent else PALETTE.accent),
            fill_opacity=0.04 if empty else (0.28 if accent else 0.1),
            stroke_width=1.5 if empty else 2.5,
        ).move_to(np.array([x, y, 0.0]))
        holds_text(box)
        piece = VGroup(box)
        if not empty:
            piece.add(_fit(Text(text, font_size=17, color=PALETTE.ink), width, height).move_to(box.get_center()))
        return piece

    y_header = total_h / 2 - header_h / 2
    left_header = cell(p.left_title, col_w, header_h, x_left, y_header, accent=True)
    right_header = cell(p.right_title, col_w, header_h, x_right, y_header, accent=True)
    divider = Line(
        np.array([(x_left + x_right) / 2, total_h / 2, 0.0]),
        np.array([(x_left + x_right) / 2, -total_h / 2, 0.0]),
        color=PALETTE.muted, stroke_width=2,
    )

    parts: dict[str, Any] = {
        "left_header": left_header, "right_header": right_header, "divider": divider,
    }
    group = VGroup(left_header, right_header, divider)

    row_names: list[str] = []
    labels = VGroup()
    for index, (left_text, right_text) in enumerate(p.rows):
        y = total_h / 2 - header_h - 0.18 - index * (row_h + 0.12) - row_h / 2
        accent = index in p.highlight
        row = VGroup(
            cell(left_text, col_w, row_h, x_left, y, accent=accent),
            cell(right_text, col_w, row_h, x_right, y, accent=accent),
        )
        name = f"row_{index + 1}"
        parts[name] = row
        row_names.append(name)
        group.add(row)
        if p.row_labels and p.row_labels[index]:
            tag = _fit(Text(p.row_labels[index], font_size=16, color=PALETTE.muted), label_w, row_h)
            tag.move_to(np.array([x_label, y, 0.0]))
            labels.add(tag)
    if p.row_labels:
        parts["labels"] = labels
        group.add(labels)

    place(group, layout("title_stage_caption")[p.region])

    highlighted = sorted(set(p.highlight))
    top = divider.get_top()
    bottom = divider.get_bottom()

    def sweep() -> Any:
        """Pulse the accented rows, or sweep a token down the whole table."""
        from manim import Dot, FadeIn, FadeOut, Indicate, Line, MoveAlongPath, Succession

        if highlighted:
            return Succession(*[
                Indicate(parts[f"row_{index + 1}"], color=PALETTE.highlight) for index in highlighted
            ])
        token = Dot(radius=0.07, color=PALETTE.highlight).move_to(top)
        return Succession(
            FadeIn(token, run_time=0.2),
            MoveAlongPath(token, Line(top, bottom)),
            FadeOut(token, run_time=0.2),
        )

    return Built(
        group=group, parts=parts,
        beats=[["left_header", "right_header", "divider"] + (["labels"] if p.row_labels else [])]
        + [[name] for name in row_names],
        motions=[sweep],
        notes=f"{count} rows: {p.left_title} vs {p.right_title}"
        + (f"; rows {[i + 1 for i in highlighted]} accented" if highlighted else ""),
    )


class HierarchyParams(BaseModel):
    """A tree given as parent-child edges."""

    edges: list[list[str]] = Field(
        min_length=1, max_length=24,
        description=(
            "Parent-child pairs, e.g. [['ML', 'supervised'], ['ML', 'unsupervised'], "
            "['supervised', 'regression']]. The root is the one label that is never a child."
        ),
    )
    highlight: list[str] = Field(
        default_factory=list,
        description="Node labels to accent, e.g. ['supervised']. Empty accents nothing.",
    )
    region: str = "stage"

    @model_validator(mode="after")
    def _a_tree(self) -> HierarchyParams:
        for index, edge in enumerate(self.edges, start=1):
            if len(edge) != 2 or not all(isinstance(end, str) and end.strip() for end in edge):
                raise ValueError(
                    f"edge {index} must be exactly two non-empty labels, a parent and a child."
                )
        children, parent = _tree_of(self.edges)
        nodes = list(children)
        if len(nodes) > 20:
            raise ValueError(f"the tree has {len(nodes)} distinct nodes; at most 20 fit on a slide.")
        roots = [node for node in nodes if node not in parent]
        if len(roots) != 1:
            raise ValueError(
                f"the tree must have exactly one root, but {roots or 'none'} never appear as children."
            )
        parents_of: dict[str, set[str]] = {}
        for source, target in self.edges:
            parents_of.setdefault(target, set()).add(source)
        for child, sources in parents_of.items():
            if len(sources) > 1:
                raise ValueError(
                    f"{child!r} has {len(sources)} parents; in a tree every node has exactly one parent."
                )
        for node, kids in children.items():
            if len(kids) > 6:
                raise ValueError(f"{node!r} has {len(kids)} children; at most 6 fit side by side.")
        levels = _levels_of(roots[0], children)
        reached = {node for level in levels for node in level}
        if reached != set(nodes):
            stranded = sorted(set(nodes) - reached)
            raise ValueError(f"the edges contain a cycle: {', '.join(stranded)} cannot be reached from the root.")
        if len(levels) > 4:
            raise ValueError(f"the tree is {len(levels)} levels deep; at most 4 levels fit on a slide.")
        for label in self.highlight:
            if label not in children:
                raise ValueError(f"highlight names {label!r}, which is not a node in the tree.")
        return self


def _tree_of(edges: list[list[str]]) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Children per node (every node keyed, first-seen order) and parent per child."""
    children: dict[str, list[str]] = {}
    parent: dict[str, str] = {}
    for source, target in edges:
        children.setdefault(source, [])
        children.setdefault(target, [])
        if target not in children[source]:
            children[source].append(target)
            parent.setdefault(target, source)
    return children, parent


def _levels_of(root: str, children: dict[str, list[str]]) -> list[list[str]]:
    levels, seen = [[root]], {root}
    while True:
        below = [kid for node in levels[-1] for kid in children[node] if kid not in seen]
        if not below:
            return levels
        seen.update(below)
        levels.append(below)


@component(version=1, domain="general", params=HierarchyParams, shape="tree")
def hierarchy(p: HierarchyParams) -> Built:
    """A tree grown from its root — taxonomies, decompositions, what contains what.

    Subtrees claim width by their leaf count and parents sit centred over their
    children, so what contains more visibly takes more room.
    """
    import numpy as np
    from manim import Line, RoundedRectangle, Text, VGroup

    children, parent = _tree_of(p.edges)
    root = next(node for node in children if node not in parent)
    levels = _levels_of(root, children)
    depth = len(levels)
    leaves = [node for node in children if not children[node]]
    slot = STAGE_W / len(leaves)
    widest = max(len(level) for level in levels)
    box_w = max(0.38, min(2.4, STAGE_W / widest - 0.3, slot - 0.12))
    box_h = 0.52
    step = min(1.7, (STAGE_H - box_h) / max(depth - 1, 1))

    x_of: dict[str, float] = {}
    cursor = {"leaf": 0}

    def spread(node: str) -> None:
        kids = children[node]
        if not kids:
            x_of[node] = -STAGE_W / 2 + slot * (cursor["leaf"] + 0.5)
            cursor["leaf"] += 1
            return
        for kid in kids:
            spread(kid)
        x_of[node] = sum(x_of[kid] for kid in kids) / len(kids)

    spread(root)

    boxes: dict[str, Any] = {}
    parts: dict[str, Any] = {}
    group = VGroup()
    beats: list[list[str]] = []
    for number, level in enumerate(levels, start=1):
        tier = VGroup()
        y = ((depth - 1) / 2 - (number - 1)) * step
        for node in level:
            accent = node in p.highlight
            box = RoundedRectangle(
                width=box_w, height=box_h, corner_radius=0.1,
                color=PALETTE.highlight if accent else PALETTE.accent,
                fill_opacity=0.28 if accent else 0.12, stroke_width=2.5,
            ).move_to(np.array([x_of[node], y, 0.0]))
            holds_text(box)
            label = _fit(Text(node, font_size=16, color=PALETTE.ink), box_w, box_h).move_to(box.get_center())
            boxes[node] = box
            tier.add(VGroup(box, label))
        parts[f"level_{number}"] = tier
        group.add(tier)
        if number == 1:
            beats.append(["level_1"])
            continue
        links = VGroup(*[
            Line(boxes[parent[node]].get_bottom(), boxes[node].get_top(),
                 buff=0.05, color=PALETTE.muted, stroke_width=2)
            for node in level
        ])
        parts[f"links_{number}"] = links
        group.add(links)
        beats.append([f"links_{number}", f"level_{number}"])

    place(group, layout("title_stage_caption")[p.region])

    chain = [levels[-1][0]]
    while chain[-1] != root:
        chain.append(parent[chain[-1]])
    trail = [boxes[node] for node in reversed(chain)]

    def descend() -> Any:
        """A dot from the root down to the deepest leaf, so depth is watched."""
        from manim import Dot, FadeIn, FadeOut, Line, MoveAlongPath, Succession

        token = Dot(radius=0.07, color=PALETTE.highlight).move_to(trail[0].get_center())
        steps: list[Any] = [FadeIn(token, run_time=0.2)]
        for above, below in pairwise(trail):
            steps.append(MoveAlongPath(token, Line(above.get_center(), below.get_center())))
        steps.append(FadeOut(token, run_time=0.2))
        return Succession(*steps)

    return Built(
        group=group, parts=parts, beats=beats, motions=[descend],
        notes=f"{len(children)} nodes over {depth} levels, root {root!r}, {len(leaves)} leaves",
    )


class LayersParams(BaseModel):
    """Bands stacked bottom-up."""

    layers: list[str] = Field(
        min_length=2, max_length=7,
        description="Band names from the bottom up, e.g. ['hardware', 'kernel', 'runtime', 'application'].",
    )
    annotations: list[str] = Field(
        default_factory=list,
        description=(
            "Optional note beside each band, e.g. ['electrons', 'syscalls', '', 'what users see']. "
            "Empty list means no notes; an empty string skips that band's note."
        ),
    )
    highlight: list[int] = Field(
        default_factory=list,
        description="Band indices to accent, counted from the bottom, e.g. [0]. Empty accents nothing.",
    )
    region: str = "stage"

    @field_validator("layers")
    @classmethod
    def _named(cls, layers: list[str]) -> list[str]:
        for index, name in enumerate(layers, start=1):
            if not name.strip():
                raise ValueError(f"layer {index} has no name; every band needs a label.")
        return layers

    @model_validator(mode="after")
    def _consistent(self) -> LayersParams:
        if self.annotations and len(self.annotations) != len(self.layers):
            raise ValueError(
                f"there are {len(self.annotations)} annotations for {len(self.layers)} layers; give one per layer or none."
            )
        for index in self.highlight:
            if not 0 <= index < len(self.layers):
                raise ValueError(
                    f"highlight index {index} is out of range for {len(self.layers)} layers."
                )
        return self


@component(version=1, domain="general", params=LayersParams, shape="stack")
def layers(p: LayersParams) -> Built:
    """Stacked bands, bottom up — a stack: architectures, abstraction levels, protocol layers.

    The build order is the meaning: each band appears on top of the ones it
    depends on, so the stack is watched being founded rather than read.
    """
    import numpy as np
    from manim import RoundedRectangle, Text, VGroup

    count = len(p.layers)
    band_w = 7.4 if p.annotations else 9.0
    band_h = min(0.85, (STAGE_H - 0.12 * (count - 1)) / count)
    x_band = -(STAGE_W - band_w) / 2 if p.annotations else 0.0

    parts: dict[str, Any] = {}
    group = VGroup()
    notes = VGroup()
    band_names: list[str] = []
    for index, name in enumerate(p.layers):
        y = (index - (count - 1) / 2) * (band_h + 0.12)
        accent = index in p.highlight
        box = RoundedRectangle(
            width=band_w, height=band_h, corner_radius=0.1,
            color=PALETTE.highlight if accent else PALETTE.accent,
            fill_opacity=0.3 if accent else 0.14, stroke_width=2.5,
        ).move_to(np.array([x_band, y, 0.0]))
        holds_text(box)
        label = _fit(Text(name, font_size=18, color=PALETTE.ink), band_w, band_h).move_to(box.get_center())
        band = VGroup(box, label)
        key = f"band_{index + 1}"
        parts[key] = band
        band_names.append(key)
        group.add(band)
        if p.annotations and p.annotations[index]:
            aside = Text(p.annotations[index], font_size=15, color=PALETTE.muted)
            aside.scale_to_fit_width(min(aside.width, 1.5))
            aside.next_to(box, np.array([1.0, 0.0, 0.0]), buff=0.25)
            notes.add(aside)
    if p.annotations:
        parts["notes"] = notes
        group.add(notes)

    place(group, layout("title_stage_caption")[p.region])

    beats = [[name] for name in band_names]
    if p.annotations:
        beats[-1] = beats[-1] + ["notes"]

    bottom_band, top_band = parts["band_1"][0], parts[band_names[-1]][0]

    def rise() -> Any:
        """A dot climbing the stack, bottom to top."""
        from manim import Dot, FadeIn, FadeOut, Line, MoveAlongPath, Succession

        token = Dot(radius=0.07, color=PALETTE.highlight).move_to(bottom_band.get_center())
        return Succession(
            FadeIn(token, run_time=0.2),
            MoveAlongPath(token, Line(bottom_band.get_center(), top_band.get_center())),
            FadeOut(token, run_time=0.2),
        )

    return Built(
        group=group, parts=parts, beats=beats, motions=[rise],
        notes=f"{count} layers, {p.layers[0]} up to {p.layers[-1]}",
    )


class GridMapParams(BaseModel):
    """Labelled cells addressed by row and column."""

    row_labels: list[str] = Field(
        min_length=1, max_length=6,
        description="One label per row, e.g. ['actual spam', 'actual ham'].",
    )
    col_labels: list[str] = Field(
        min_length=1, max_length=6,
        description="One label per column, e.g. ['predicted spam', 'predicted ham'].",
    )
    cells: list[list[str]] = Field(
        description=(
            "Cell text by [row][column], e.g. [['90', '10'], ['5', '95']]. "
            "An empty string draws a blank cell."
        ),
    )
    highlight: list[list[int]] = Field(
        default_factory=list,
        description="Cells to accent as [row, column] pairs, e.g. [[0, 0], [1, 1]]. Empty accents nothing.",
    )
    region: str = "stage"

    @model_validator(mode="after")
    def _rectangular(self) -> GridMapParams:
        if len(self.cells) != len(self.row_labels):
            raise ValueError(
                f"there are {len(self.cells)} rows of cells for {len(self.row_labels)} row labels; they must match."
            )
        for index, row in enumerate(self.cells, start=1):
            if len(row) != len(self.col_labels):
                raise ValueError(
                    f"row {index} of cells has {len(row)} entries but there are {len(self.col_labels)} column labels; every row must match the columns."
                )
        for pair in self.highlight:
            if len(pair) != 2:
                raise ValueError("each highlight must be a [row, column] pair.")
            row, column = pair
            if not (0 <= row < len(self.row_labels) and 0 <= column < len(self.col_labels)):
                raise ValueError(
                    f"highlight [{row}, {column}] is outside a {len(self.row_labels)}x{len(self.col_labels)} grid."
                )
        return self


@component(version=1, domain="general", params=GridMapParams, shape="grid")
def grid_map(p: GridMapParams) -> Built:
    """Labelled cells in rows and columns — a matrix, a table, a confusion matrix, a state space.

    The grid fills row by row, and the cells that carry the argument are rung
    with an accent afterwards, so the eye lands where the numbers matter.
    """
    import numpy as np
    from manim import RoundedRectangle, Text, VGroup

    rows, cols = len(p.row_labels), len(p.col_labels)
    gap = 0.1
    cell_w = min(2.3, STAGE_W / (cols + 1) - gap)
    cell_h = min(0.65, STAGE_H / (rows + 1) - gap)

    def x_at(column: int) -> float:
        """Column 0 is the row-label column; data columns follow."""
        return (column - cols / 2) * (cell_w + gap)

    def y_at(row: int) -> float:
        """Row 0 is the column-header row; data rows follow."""
        return (rows / 2 - row) * (cell_h + gap)

    def cell(text: str, x: float, y: float, *, header: bool) -> VGroup:
        empty = not text
        box = RoundedRectangle(
            width=cell_w, height=cell_h, corner_radius=0.08,
            color=PALETTE.muted if empty else PALETTE.accent,
            fill_opacity=0.04 if empty else (0.22 if header else 0.12),
            stroke_width=1.5 if empty else 2,
        ).move_to(np.array([x, y, 0.0]))
        holds_text(box)
        piece = VGroup(box)
        if not empty:
            piece.add(_fit(Text(text, font_size=16, color=PALETTE.ink), cell_w, cell_h).move_to(box.get_center()))
        return piece

    col_headers = VGroup(*[
        cell(name, x_at(column + 1), y_at(0), header=True) for column, name in enumerate(p.col_labels)
    ])
    row_headers = VGroup(*[
        cell(name, x_at(0), y_at(row + 1), header=True) for row, name in enumerate(p.row_labels)
    ])
    parts: dict[str, Any] = {"col_headers": col_headers, "row_headers": row_headers}
    group = VGroup(col_headers, row_headers)

    row_names: list[str] = []
    for row, values in enumerate(p.cells):
        line = VGroup(*[
            cell(text, x_at(column + 1), y_at(row + 1), header=False)
            for column, text in enumerate(values)
        ])
        name = f"row_{row + 1}"
        parts[name] = line
        row_names.append(name)
        group.add(line)

    accents = VGroup()
    for row, column in p.highlight:
        ring = RoundedRectangle(
            width=cell_w, height=cell_h, corner_radius=0.08,
            color=PALETTE.highlight, fill_opacity=0.0, stroke_width=3.5,
        ).move_to(np.array([x_at(column + 1), y_at(row + 1), 0.0]))
        holds_text(ring)
        accents.add(ring)
    if p.highlight:
        parts["accents"] = accents
        group.add(accents)

    place(group, layout("title_stage_caption")[p.region])

    rings = list(accents)

    def pulse() -> Any:
        """Each accented cell flares in turn."""
        from manim import Indicate, Succession

        return Succession(*[Indicate(ring, color=PALETTE.highlight) for ring in rings])

    filled = sum(1 for row in p.cells for text in row if text)
    return Built(
        group=group, parts=parts,
        beats=[["col_headers", "row_headers"]] + [[name] for name in row_names]
        + ([["accents"]] if p.highlight else []),
        motions=[pulse] if p.highlight else [],
        notes=f"{rows}x{cols} grid, {filled} of {rows * cols} cells filled"
        + (f"; {len(p.highlight)} accented" if p.highlight else ""),
    )
