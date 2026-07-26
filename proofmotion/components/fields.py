"""Circuits, optics, fields, and thermodynamic state diagrams.

The four physics patterns that are hardest to place by hand, because each is a
diagram with a strict convention: a ray diagram that violates the thin-lens
equation is wrong even if it looks tidy, and a P-V cycle that does not close is
not a cycle.
"""

from __future__ import annotations

import itertools
import math
from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.components.mechanics import _annotate
from proofmotion.layout.regions import layout, place
from proofmotion.runtime.registry import ToolError

WIRE = "#94a3b8"
BODY = "#4aa3df"
HIGHLIGHT = "#fbbf24"
ACCENT = "#4ade80"
FORCE = "#f87171"


class CircuitParams(BaseModel):
    voltage: float = Field(default=9.0, description="Source EMF in volts.")
    resistances: list = Field(min_length=1, max_length=4, description="Resistances in ohms.")
    arrangement: Literal["series", "parallel"] = "series"
    region: str = "stage"


@component(version=1, domain="physics", params=CircuitParams)
def circuit_diagram(p: CircuitParams) -> Built:
    """A DC circuit with the total resistance and current solved for.

    Series and parallel combine differently, and the current shown is the one
    that follows from the arrangement rather than the one intended.
    """
    import numpy as np
    from manim import Line, Rectangle, VGroup

    values = [float(r) for r in p.resistances]
    if any(r <= 0 for r in values):
        raise ToolError("resistances must be positive")
    total = sum(values) if p.arrangement == "series" else 1.0 / sum(1.0 / r for r in values)
    current = p.voltage / total

    left, right, top, bottom = -3.6, 3.6, 1.5, -1.5
    wires = VGroup(
        Line(np.array([left, bottom, 0]), np.array([left, top, 0]), color=WIRE, stroke_width=3),
        Line(np.array([left, top, 0]), np.array([right, top, 0]), color=WIRE, stroke_width=3),
        Line(np.array([right, top, 0]), np.array([right, bottom, 0]), color=WIRE, stroke_width=3),
        Line(np.array([right, bottom, 0]), np.array([left, bottom, 0]), color=WIRE, stroke_width=3),
    )
    battery = VGroup(
        Line(np.array([left - 0.28, 0.3, 0]), np.array([left + 0.28, 0.3, 0]), stroke_width=6, color=HIGHLIGHT),
        Line(np.array([left - 0.16, -0.05, 0]), np.array([left + 0.16, -0.05, 0]), stroke_width=3, color=HIGHLIGHT),
    )

    parts: dict[str, Any] = {"wires": wires, "battery": battery}
    group = VGroup(wires, battery)
    beats = [["wires"], ["battery"]]

    resistors = VGroup()
    positions = []
    if p.arrangement == "series":
        for index, value in enumerate(values):
            x = left + (right - left) * (index + 1) / (len(values) + 1)
            box = Rectangle(width=0.9, height=0.36, color=BODY, fill_opacity=0.3, stroke_width=2.4)
            box.move_to(np.array([x, top, 0]))
            resistors.add(box)
            positions.append((box, value))
    else:
        for index, value in enumerate(values):
            y = top - (top - bottom) * (index + 1) / (len(values) + 1)
            box = Rectangle(width=0.36, height=0.9, color=BODY, fill_opacity=0.3, stroke_width=2.4)
            box.move_to(np.array([0.0, y, 0]))
            resistors.add(box)
            positions.append((box, value))
            resistors.add(
                Line(np.array([left, y, 0]), np.array([-0.18, y, 0]), color=WIRE, stroke_width=2),
                Line(np.array([0.18, y, 0]), np.array([right, y, 0]), color=WIRE, stroke_width=2),
            )
    parts["resistors"] = resistors
    group.add(resistors)
    beats.append(["resistors"])

    obstacles = [wires, battery, resistors]
    placed: list[Any] = []
    labels: list[str] = []
    for index, (box, value) in enumerate(positions):
        _annotate(box.get_center(), rf"{value:g}\,\Omega", obstacles, placed, parts, group, labels,
                  f"resistor_label_{index}", BODY)
    _annotate(np.array([left - 0.9, 0.1, 0.0]), rf"{p.voltage:g}\,\text{{V}}",
              obstacles, placed, parts, group, labels, "voltage_label", HIGHLIGHT)
    _annotate(np.array([0.0, bottom - 0.9, 0.0]),
              rf"R_{{\text{{eq}}}}={total:.3f}\,\Omega,\ I={current:.3f}\,\text{{A}}",
              obstacles, placed, parts, group, labels, "solution_label", ACCENT)
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=f"{p.arrangement}: R_eq={total:.6f} ohm, I={current:.6f} A from V={p.voltage:g}",
    )


class RayDiagramParams(BaseModel):
    focal_length: float = Field(default=1.5, description="Positive for a converging lens, negative for diverging.")
    object_distance: float = Field(default=3.0, gt=0, description="Distance in front of the lens.")
    object_height: float = Field(default=1.0, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=RayDiagramParams)
def ray_diagram(p: RayDiagramParams) -> Built:
    """A thin-lens ray diagram with the image solved from 1/f = 1/u + 1/v.

    The image position and height come from the lens equation, so the rays and
    the arithmetic agree. A virtual image is drawn on the correct side and
    reported as virtual rather than silently placed like a real one.
    """
    import numpy as np
    from manim import Arrow, DashedLine, Dot, Ellipse, Line, VGroup

    f, u = float(p.focal_length), float(p.object_distance)
    if abs(u - f) < 1e-6:
        raise ToolError("the object sits at the focal point, so no image forms")
    v = 1.0 / (1.0 / f - 1.0 / u)          # image distance, signed
    magnification = -v / u
    image_height = p.object_height * magnification
    real = v > 0

    scale = min(1.5, 4.4 / max(u, abs(v), 1e-6))
    axis = Line(np.array([-5.4, 0, 0]), np.array([5.4, 0, 0]), stroke_width=2, color="#475569")
    lens = Ellipse(width=0.42, height=3.1, color=BODY, fill_opacity=0.18, stroke_width=2.5)
    focal_near = Dot(np.array([-abs(f) * scale, 0, 0]), radius=0.06, color=HIGHLIGHT)
    focal_far = Dot(np.array([abs(f) * scale, 0, 0]), radius=0.06, color=HIGHLIGHT)

    object_x = -u * scale
    object_arrow = Arrow(np.array([object_x, 0, 0]), np.array([object_x, p.object_height * scale, 0]),
                         buff=0, stroke_width=4, color=ACCENT)
    image_x = v * scale
    image_arrow = Arrow(np.array([image_x, 0, 0]), np.array([image_x, image_height * scale, 0]),
                        buff=0, stroke_width=4, color=FORCE)

    top_of_object = np.array([object_x, p.object_height * scale, 0])
    parallel_in = Line(top_of_object, np.array([0, p.object_height * scale, 0]), stroke_width=2, color="#cbd5e1")
    through_focus = Line(np.array([0, p.object_height * scale, 0]),
                         np.array([image_x, image_height * scale, 0]), stroke_width=2, color="#cbd5e1")
    centre_ray = Line(top_of_object, np.array([image_x, image_height * scale, 0]), stroke_width=2, color="#cbd5e1")

    parts: dict[str, Any] = {
        "axis": axis, "lens": lens, "focus_near": focal_near, "focus_far": focal_far,
        "object": object_arrow, "image": image_arrow,
        "ray_parallel": parallel_in, "ray_focus": through_focus, "ray_centre": centre_ray,
    }
    group = VGroup(axis, lens, focal_near, focal_far, object_arrow,
                   parallel_in, through_focus, centre_ray, image_arrow)
    beats = [["axis", "lens", "focus_near", "focus_far"], ["object"],
             ["ray_parallel", "ray_focus", "ray_centre"], ["image"]]

    if not real:
        extension = DashedLine(np.array([0, p.object_height * scale, 0]),
                               np.array([image_x, image_height * scale, 0]),
                               stroke_width=1.8, color="#64748b")
        parts["virtual_extension"] = extension
        group.add(extension)
        beats[2].append("virtual_extension")

    obstacles = [axis, lens, object_arrow, image_arrow, parallel_in, through_focus, centre_ray]
    if "virtual_extension" in parts:
        obstacles.append(parts["virtual_extension"])
    placed: list[Any] = []
    labels: list[str] = []
    _annotate(object_arrow.get_end(), r"\text{object}", obstacles, placed, parts, group, labels, "object_label", ACCENT)
    _annotate(image_arrow.get_end(), rf"\text{{{'real' if real else 'virtual'}}}",
              obstacles, placed, parts, group, labels, "image_label", FORCE)
    _annotate(np.array([0.0, -2.3, 0.0]),
              rf"\frac{{1}}{{f}}=\frac{{1}}{{u}}+\frac{{1}}{{v}}:\ v={v:.3f},\ m={magnification:.3f}",
              obstacles, placed, parts, group, labels, "lens_equation", HIGHLIGHT)
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=(
            f"f={f:g}, u={u:g} -> v={v:.6f} ({'real' if real else 'virtual'}), "
            f"magnification {magnification:.6f}, image height {image_height:.6f}"
        ),
    )


class FieldLinesParams(BaseModel):
    charges: list = Field(min_length=1, max_length=4,
                          description='Charges as [x, y, q], e.g. [[-1, 0, 1], [1, 0, -1]] for a dipole.')
    lines_per_charge: int = Field(default=10, ge=4, le=20)
    region: str = "stage"


@component(version=1, domain="physics", params=FieldLinesParams)
def field_lines(p: FieldLinesParams) -> Built:
    """Electric field lines traced from point charges.

    Lines are integrated along the actual field, so they leave positive charges,
    enter negative ones, and never cross — which a hand-drawn dipole often does.
    """
    import numpy as np
    from manim import Dot, VGroup, VMobject

    charges = [(float(c[0]), float(c[1]), float(c[2])) for c in p.charges]
    if all(abs(q) < 1e-12 for *_, q in charges):
        raise ToolError("at least one charge must be non-zero")

    def field(x: float, y: float) -> tuple[float, float]:
        ex = ey = 0.0
        for cx, cy, q in charges:
            dx, dy = x - cx, y - cy
            r2 = dx * dx + dy * dy
            if r2 < 4e-3:
                return 0.0, 0.0
            r3 = r2 ** 1.5
            ex += q * dx / r3
            ey += q * dy / r3
        return ex, ey

    traces = VGroup()
    for cx, cy, q in charges:
        if abs(q) < 1e-12:
            continue
        direction = 1.0 if q > 0 else -1.0
        for k in range(p.lines_per_charge):
            angle = 2 * math.pi * k / p.lines_per_charge
            x, y = cx + 0.22 * math.cos(angle), cy + 0.22 * math.sin(angle)
            points = [np.array([x, y, 0.0])]
            for _ in range(240):
                ex, ey = field(x, y)
                magnitude = math.hypot(ex, ey)
                if magnitude < 1e-9:
                    break
                x += direction * 0.045 * ex / magnitude
                y += direction * 0.045 * ey / magnitude
                if abs(x) > 4.2 or abs(y) > 2.6:
                    break
                if any(math.hypot(x - ox, y - oy) < 0.2 and oq * q < 0 for ox, oy, oq in charges):
                    points.append(np.array([x, y, 0.0]))
                    break
                points.append(np.array([x, y, 0.0]))
            if len(points) > 3:
                curve = VMobject(stroke_width=1.9, stroke_opacity=0.75,
                                 color=FORCE if q > 0 else BODY)
                curve.set_points_smoothly(points)
                traces.add(curve)

    if not len(traces):
        raise ToolError("no field lines could be traced from these charges")

    markers = VGroup(*[
        Dot(np.array([cx, cy, 0.0]), radius=0.13, color=FORCE if q > 0 else BODY)
        for cx, cy, q in charges
    ])
    parts: dict[str, Any] = {"lines": traces, "charges": markers}
    group = VGroup(traces, markers)
    beats = [["charges"], ["lines"]]

    # A single charge radiates lines in every direction, so no position beside it
    # is clear. Sign is carried by colour, and one legend states the convention.
    placed: list[Any] = []
    labels: list[str] = []
    legend = "+" if all(q > 0 for *_, q in charges) else "-" if all(q < 0 for *_, q in charges) else "+/-"
    _annotate(np.array([0.0, 2.9, 0.0]),
              rf"\text{{red}}=+,\ \text{{blue}}=-\quad({legend})",
              [traces, markers], placed, parts, group, labels, "legend")
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    total = sum(q for *_, q in charges)
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"{len(charges)} charges, net {total:g}, {len(traces)} traced lines")


class PVDiagramParams(BaseModel):
    states: list = Field(min_length=2, max_length=6,
                         description='States as [pressure, volume], e.g. [[3,1],[1,3],[1,1]].')
    labels: list = Field(default_factory=list, description="Optional name per state.")
    close_cycle: bool = True
    region: str = "stage"


@component(version=1, domain="physics", params=PVDiagramParams)
def pv_diagram(p: PVDiagramParams) -> Built:
    """A pressure-volume path, with the enclosed work computed by the shoelace area.

    For a closed cycle the work is the area, and its sign tells you whether the
    cycle is an engine or a refrigerator — computed here rather than asserted.
    """
    from manim import Axes, Dot, VGroup, VMobject

    points = [(float(s[1]), float(s[0])) for s in p.states]   # (volume, pressure)
    volumes = [v for v, _ in points]
    pressures = [q for _, q in points]
    path_points = [*points, points[0]] if p.close_cycle else points

    axes = Axes(
        x_range=[0, max(volumes) * 1.25, max(volumes) / 4],
        y_range=[0, max(pressures) * 1.25, max(pressures) / 4],
        x_length=7.4, y_length=4.0, tips=False,
        axis_config={"include_numbers": True, "color": "#9aa7bd", "font_size": 20},
    )
    path = VMobject(stroke_width=3.5, color=BODY)
    path.set_points_as_corners([axes.c2p(v, q) for v, q in path_points])
    markers = VGroup(*[Dot(axes.c2p(v, q), radius=0.07, color=HIGHLIGHT) for v, q in points])

    # Shoelace: positive for a clockwise loop, which is net work done by the gas.
    work = 0.0
    if p.close_cycle and len(points) >= 3:
        # pairwise: the pair list is one shorter than the point list, so strict
        # zipping raised rather than walking the edges.
        for (v1, q1), (v2, q2) in itertools.pairwise(path_points):
            work += (v1 * q2 - v2 * q1)
        work = -work / 2.0

    parts: dict[str, Any] = {"axes": axes, "path": path, "states": markers}
    group = VGroup(axes, path, markers)
    beats = [["axes"], ["path"], ["states"]]

    obstacles = [axes, path]
    placed: list[Any] = []
    labels: list[str] = []
    for index, (v, q) in enumerate(points):
        name = p.labels[index] if index < len(p.labels) else chr(ord("A") + index)
        _annotate(axes.c2p(v, q), name, obstacles, placed, parts, group, labels, f"state_{index}", HIGHLIGHT)
    if p.close_cycle and len(points) >= 3:
        kind = "engine" if work > 0 else "refrigerator"
        _annotate(axes.c2p(max(volumes) * 0.55, max(pressures) * 1.05),
                  rf"W={work:.3f}\ (\text{{{kind}}})", obstacles, placed, parts, group, labels, "work_label", ACCENT)
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=(f"{len(points)} states; enclosed work {work:.6f} "
               f"({'clockwise, engine' if work > 0 else 'anticlockwise, refrigerator' if work else 'open path'})"),
    )
