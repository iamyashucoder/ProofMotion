"""Physics components.

The prompt that exposed the need for these — a bead on a vertical loop, with
N(theta) and energy conservation — had no component to fall back on, so the
coder hand-placed every arrow and label. It spent 39 signature lookups and still
produced truncated code.

Each component here computes its own physics rather than accepting numbers on
trust, and places its labels with the scorer, so a free-body diagram cannot end
up with "mg" written across the weight arrow.
"""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.labels import place_label
from proofmotion.layout.regions import layout, place

GRAVITY = 9.81
#: Longest force arrow, in scene units. Everything scales relative to this so a
#: 500 N force and a 5 N force stay on screen together.
MAX_ARROW = 1.7
BODY_COLOR = "#4aa3df"
FORCE_COLORS = ("#f87171", "#4ade80", "#fbbf24", "#a78bfa", "#38bdf8", "#fb923c")


class Force(BaseModel):
    label: str = Field(description="LaTeX for the force, e.g. 'mg' or 'N'.")
    magnitude: float = Field(gt=0, description="Relative size; only ratios matter for the drawing.")
    angle_deg: float = Field(description="Direction in degrees, measured anticlockwise from east.")


def _arrow(origin, force: Force, scale: float, colour: str):
    import numpy as np
    from manim import Arrow

    length = max(0.35, MAX_ARROW * force.magnitude * scale)
    radians = math.radians(force.angle_deg)
    tip = origin + np.array([length * math.cos(radians), length * math.sin(radians), 0.0])
    return Arrow(origin, tip, buff=0, stroke_width=4, max_tip_length_to_length_ratio=0.28, color=colour)


def _label_forces(arrows: dict[str, object], forces: list[Force], avoid: list, parts: dict, group, beats_row: list):
    """Attach each force label to its own arrow tip, scored against everything drawn."""
    from manim import MathTex

    placed = []
    for index, force in enumerate(forces):
        arrow = arrows[f"force_{index}"]
        text = MathTex(force.label, font_size=26, color=arrow.get_color())
        result = place_label(text, arrow.get_end(), avoid=avoid, placed=placed)
        parts[f"label_{index}"] = text
        group.add(text)
        beats_row.append(f"label_{index}")
        placed.append(text)
        if result["leader"] is not None:
            parts[f"leader_{index}"] = result["leader"]
            group.add(result["leader"])
            beats_row.append(f"leader_{index}")


class FreeBodyParams(BaseModel):
    body: str = Field(default="m", description="LaTeX label for the body itself.")
    forces: list[Force] = Field(min_length=1, max_length=6)
    shape: Literal["box", "dot", "circle"] = "box"
    region: str = "stage"


@component(version=1, domain="physics", params=FreeBodyParams)
def free_body_diagram(p: FreeBodyParams) -> Built:
    """A body with force arrows, each labelled clear of the geometry."""
    import numpy as np
    from manim import Circle, Dot, MathTex, Square, VGroup

    origin = np.array([0.0, 0.0, 0.0])
    if p.shape == "box":
        body = Square(side_length=0.9, color=BODY_COLOR, fill_opacity=0.35)
    elif p.shape == "circle":
        body = Circle(radius=0.45, color=BODY_COLOR, fill_opacity=0.35)
    else:
        body = Dot(origin, radius=0.11, color=BODY_COLOR)
    body.move_to(origin)

    biggest = max(f.magnitude for f in p.forces)
    arrows = {
        f"force_{i}": _arrow(origin, f, 1.0 / biggest, FORCE_COLORS[i % len(FORCE_COLORS)])
        for i, f in enumerate(p.forces)
    }
    body_text = MathTex(p.body, font_size=26)
    if p.shape == "dot":
        # A dot has no interior to write in, so the label sits beside it.
        place_label(body_text, origin, avoid=[body, *arrows.values()])
    else:
        body_text.move_to(origin)

    group = VGroup(body, body_text, *arrows.values())
    parts = {"body": body, "body_label": body_text, **arrows}
    beats = [["body", "body_label"], list(arrows)]
    _label_forces(arrows, p.forces, [body, *arrows.values()], parts, group, beats[-1])

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"{len(p.forces)} forces, scaled to the largest")


class CircularMotionParams(BaseModel):
    radius: float = Field(default=1.6, gt=0.2, le=3.0, description="Drawn radius in scene units.")
    angle_deg: float = Field(default=60.0, description="Position on the circle, anticlockwise from east.")
    show_weight: bool = True
    show_normal: bool = Field(default=True, description="Normal/tension along the radius, toward the centre.")
    show_velocity: bool = Field(default=True, description="Tangential velocity.")
    label_angle: str = Field(default=r"\theta", description="LaTeX for the angle label.")
    region: str = "stage"


@component(version=1, domain="physics", params=CircularMotionParams)
def circular_motion(p: CircularMotionParams) -> Built:
    """A body on a circular path with radial and tangential vectors.

    Covers vertical loops, conical pendulums, and orbits: the forces are drawn
    along the true radius and tangent at the chosen angle, so the diagram stays
    correct as the angle changes.
    """
    import numpy as np
    from manim import Angle, Arrow, Circle, DashedLine, Dot, Line, MathTex, VGroup

    centre = np.array([0.0, 0.0, 0.0])
    radians = math.radians(p.angle_deg)
    position = centre + np.array([p.radius * math.cos(radians), p.radius * math.sin(radians), 0.0])

    track = Circle(radius=p.radius, color="#64748b", stroke_width=3).move_to(centre)
    spoke = DashedLine(centre, position, stroke_width=2, color="#94a3b8")
    baseline = Line(centre, centre + np.array([p.radius, 0.0, 0.0]), stroke_width=2, color="#94a3b8")
    hub = Dot(centre, radius=0.05, color="#94a3b8")
    bead = Dot(position, radius=0.1, color=BODY_COLOR)

    parts = {"track": track, "spoke": spoke, "baseline": baseline, "hub": hub, "bead": bead}
    group = VGroup(track, baseline, hub, spoke, bead)
    beats = [["track", "baseline", "hub"], ["spoke", "bead"]]

    if abs(p.angle_deg % 360) > 1e-6:
        arc = Angle(baseline, Line(centre, position), radius=min(0.55, p.radius * 0.4), color="#fbbf24")
        parts["angle_arc"] = arc
        group.add(arc)
        beats[1].append("angle_arc")

    vectors: dict[str, object] = {}
    inward = (centre - position) / np.linalg.norm(centre - position)
    if p.show_normal:
        vectors["normal"] = Arrow(position, position + inward * 1.0, buff=0, stroke_width=4, color="#4ade80")
    if p.show_weight:
        vectors["weight"] = Arrow(position, position + np.array([0.0, -1.0, 0.0]), buff=0, stroke_width=4, color="#f87171")
    if p.show_velocity:
        tangent = np.array([-inward[1], inward[0], 0.0])
        vectors["velocity"] = Arrow(position, position + tangent * 0.95, buff=0, stroke_width=4, color="#38bdf8")

    parts.update(vectors)
    group.add(*vectors.values())
    if vectors:
        beats.append(list(vectors))

    # The arc must be in `avoid`: the inward normal ends near the centre, which is
    # exactly where the angle arc lives, and N landed on it at several angles.
    avoid = [track, spoke, baseline, *vectors.values()]
    if "angle_arc" in parts:
        avoid.append(parts["angle_arc"])
    placed = []
    naming = {"normal": "N", "weight": "mg", "velocity": "v"}
    for key, arrow in vectors.items():
        text = MathTex(naming[key], font_size=26, color=arrow.get_color())
        result = place_label(text, arrow.get_end(), avoid=avoid, placed=placed)
        parts[f"{key}_label"] = text
        group.add(text)
        beats[-1].append(f"{key}_label")
        placed.append(text)
        if result["leader"] is not None:
            parts[f"{key}_leader"] = result["leader"]
            group.add(result["leader"])
            beats[-1].append(f"{key}_leader")

    if "angle_arc" in parts:
        angle_text = MathTex(p.label_angle, font_size=26, color="#fbbf24")
        mid = math.radians(p.angle_deg / 2)
        anchor = centre + np.array([math.cos(mid), math.sin(mid), 0.0]) * min(0.85, p.radius * 0.62)
        result = place_label(angle_text, anchor, avoid=avoid, placed=placed)
        parts["angle_label"] = angle_text
        group.add(angle_text)
        beats[1].append("angle_label")
        if result["leader"] is not None:
            parts["angle_leader"] = result["leader"]
            group.add(result["leader"])

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"angle {p.angle_deg} deg, radius {p.radius}")


class ProjectileParams(BaseModel):
    speed: float = Field(gt=0, description="Launch speed in m/s.")
    angle_deg: float = Field(gt=0, lt=90, description="Launch angle above the horizontal.")
    gravity: float = Field(default=GRAVITY, gt=0)
    show_components: bool = Field(default=True, description="Draw the launch velocity components.")
    region: str = "stage"


@component(version=1, domain="physics", params=ProjectileParams)
def projectile_motion(p: ProjectileParams) -> Built:
    """A projectile trajectory with range and apex computed, not assumed."""
    import numpy as np
    from manim import Arrow, Axes, DashedLine, Dot, MathTex, VGroup

    radians = math.radians(p.angle_deg)
    vx, vy = p.speed * math.cos(radians), p.speed * math.sin(radians)
    flight = 2 * vy / p.gravity
    distance = vx * flight
    apex = vy**2 / (2 * p.gravity)

    axes = Axes(
        x_range=[0, distance * 1.08, max(distance / 5, 1e-6)],
        y_range=[0, max(apex * 1.35, 1e-6), max(apex / 3, 1e-6)],
        x_length=8.4, y_length=3.9, tips=False,
        axis_config={"include_numbers": True, "color": "#9aa7bd", "font_size": 20},
    )
    # y = x tan(theta) - g x^2 / (2 v_x^2). Not 2 v_x^2 cos^2(theta): v_x already
    # carries the cosine, and the duplicate made the parabola fall far below the
    # axes, which showed up as the whole figure being scaled to nothing.
    path = axes.plot(
        lambda x: x * math.tan(radians) - p.gravity * x**2 / (2 * vx**2),
        x_range=[0, distance], color=BODY_COLOR,
    )
    top = Dot(axes.c2p(distance / 2, apex), radius=0.07, color="#fbbf24")
    guide = DashedLine(axes.c2p(distance / 2, 0), axes.c2p(distance / 2, apex), stroke_width=2, color="#64748b")

    parts = {"axes": axes, "path": path, "apex": top, "apex_guide": guide}
    group = VGroup(axes, path, guide, top)
    beats = [["axes"], ["path"], ["apex_guide", "apex"]]

    if p.show_components:
        origin = axes.c2p(0, 0)
        scale = min(1.3, distance / max(p.speed, 1e-6))
        horizontal = Arrow(origin, origin + np.array([vx * scale * 0.12, 0, 0]), buff=0, stroke_width=4, color="#4ade80")
        vertical = Arrow(origin, origin + np.array([0, vy * scale * 0.12, 0]), buff=0, stroke_width=4, color="#f87171")
        parts.update({"vx": horizontal, "vy": vertical})
        group.add(horizontal, vertical)
        beats.append(["vx", "vy"])

    # Readouts are not point labels. Anchoring "R=..." at the end of the x-axis
    # and "h=..." on the apex dot left every candidate position touching
    # geometry, so both landed on it. They belong in clear space instead.
    # Steep launches leave no clear space inside the plot, so hunting for a gap
    # there just found the least-bad collision. Outside the axes there is always
    # room, and place() scales the taller group to fit its region.
    readouts = VGroup(
        MathTex(rf"R={distance:.2f}\,\text{{m}}", font_size=25),
        MathTex(rf"h={apex:.2f}\,\text{{m}}", font_size=25),
    ).arrange(np.array([1.0, 0.0, 0.0]), buff=0.6)
    readouts.next_to(axes, np.array([0.0, 1.0, 0.0]), buff=0.28)
    parts["readouts"] = readouts
    group.add(readouts)
    beats.append(["readouts"])

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=f"range {distance:.4f} m, apex {apex:.4f} m, flight {flight:.4f} s",
    )


class InclinedPlaneParams(BaseModel):
    angle_deg: float = Field(gt=1, lt=80, description="Slope angle above the horizontal.")
    show_components: bool = Field(default=True, description="Resolve the weight along and into the slope.")
    show_friction: bool = False
    region: str = "stage"


@component(version=1, domain="physics", params=InclinedPlaneParams)
def inclined_plane(p: InclinedPlaneParams) -> Built:
    """A block on a slope with the weight resolved along and perpendicular to it."""
    import numpy as np
    from manim import Angle, Arrow, Line, MathTex, Polygon, Square, VGroup

    radians = math.radians(p.angle_deg)
    base = 5.0
    height = base * math.tan(radians)
    if height > 3.0:  # keep steep slopes on screen
        height, base = 3.0, 3.0 / math.tan(radians)

    corner = np.array([-base / 2, -height / 2, 0.0])
    top = np.array([-base / 2, height / 2, 0.0])
    foot = np.array([base / 2, -height / 2, 0.0])
    ramp = Polygon(corner, foot, top, color="#64748b", stroke_width=3, fill_opacity=0.12)
    slope_line = Line(top, foot)

    along = (foot - top) / np.linalg.norm(foot - top)
    normal_dir = np.array([-along[1], along[0], 0.0])
    seat = top + along * (np.linalg.norm(foot - top) * 0.42)
    block = Square(side_length=0.62, color=BODY_COLOR, fill_opacity=0.4).rotate(-radians).move_to(seat + normal_dir * 0.31)

    weight = Arrow(block.get_center(), block.get_center() + np.array([0, -1.15, 0]), buff=0, stroke_width=4, color="#f87171")
    normal = Arrow(block.get_center(), block.get_center() + normal_dir * 0.95, buff=0, stroke_width=4, color="#4ade80")

    parts = {"ramp": ramp, "block": block, "weight": weight, "normal": normal}
    group = VGroup(ramp, block, weight, normal)
    beats = [["ramp"], ["block"], ["weight", "normal"]]
    vectors = [weight, normal]

    if p.show_components:
        parallel = Arrow(block.get_center(), block.get_center() + along * 0.95, buff=0, stroke_width=3.4, color="#fbbf24")
        parts["w_parallel"] = parallel
        group.add(parallel)
        beats.append(["w_parallel"])
        vectors.append(parallel)
    if p.show_friction:
        friction = Arrow(block.get_center(), block.get_center() - along * 0.8, buff=0, stroke_width=3.4, color="#a78bfa")
        parts["friction"] = friction
        group.add(friction)
        beats[-1].append("friction")
        vectors.append(friction)

    arc = Angle(Line(corner, foot), Line(corner, top), radius=0.6, color="#fbbf24")
    parts["angle_arc"] = arc
    group.add(arc)
    beats[0].append("angle_arc")

    avoid = [ramp, block, slope_line, *vectors]
    placed = []
    naming = [(weight, "mg"), (normal, "N")]
    if p.show_components:
        naming.append((parts["w_parallel"], r"mg\sin\theta"))
    if p.show_friction:
        naming.append((parts["friction"], "f"))
    for index, (arrow, tex) in enumerate(naming):
        text = MathTex(tex, font_size=25, color=arrow.get_color())
        result = place_label(text, arrow.get_end(), avoid=avoid, placed=placed)
        parts[f"label_{index}"] = text
        group.add(text)
        beats[-1].append(f"label_{index}")
        placed.append(text)
        if result["leader"] is not None:
            parts[f"leader_{index}"] = result["leader"]
            group.add(result["leader"])

    theta = MathTex(r"\theta", font_size=26, color="#fbbf24")
    place_label(theta, corner + np.array([0.85, 0.22, 0.0]), avoid=avoid, placed=placed)
    parts["angle_label"] = theta
    group.add(theta)
    beats[0].append("angle_label")

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"slope {p.angle_deg} deg")


class EnergyBarsParams(BaseModel):
    entries: dict[str, float] = Field(description='Named energies, e.g. {"KE": 12.0, "PE": 8.0}.')
    unit: str = Field(default="J")
    show_total: bool = True
    region: str = "stage"


@component(version=1, domain="physics", params=EnergyBarsParams)
def energy_bars(p: EnergyBarsParams) -> Built:
    """A bar per energy term, with the total, for conservation arguments."""
    import numpy as np
    from manim import MathTex, Rectangle, Text, VGroup

    if not p.entries:
        from proofmotion.runtime.registry import ToolError

        raise ToolError("energy_bars needs at least one entry")

    items = list(p.entries.items())
    if p.show_total:
        items.append(("Total", sum(p.entries.values())))
    biggest = max(abs(v) for _, v in items) or 1.0

    bar_width, gap, tallest = 1.0, 0.55, 2.9
    parts: dict[str, object] = {}
    group = VGroup()
    reveal: list[str] = []
    for index, (name, value) in enumerate(items):
        height = max(0.08, tallest * abs(value) / biggest)
        colour = FORCE_COLORS[index % len(FORCE_COLORS)] if name != "Total" else "#e2e8f0"
        bar = Rectangle(width=bar_width, height=height, color=colour, fill_opacity=0.55, stroke_width=2)
        bar.move_to(np.array([(index - (len(items) - 1) / 2) * (bar_width + gap), height / 2 - tallest / 2, 0.0]))
        name_text = Text(name, font_size=22).next_to(bar, np.array([0.0, -1.0, 0.0]), buff=0.16)
        value_text = MathTex(rf"{value:g}\,\text{{{p.unit}}}", font_size=22).next_to(bar, np.array([0.0, 1.0, 0.0]), buff=0.14)
        parts[f"bar_{index}"] = bar
        parts[f"name_{index}"] = name_text
        parts[f"value_{index}"] = value_text
        group.add(bar, name_text, value_text)
        reveal += [f"bar_{index}", f"name_{index}", f"value_{index}"]

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[reveal], notes=f"{len(items)} bars, largest {biggest:g} {p.unit}")


class WaveParams(BaseModel):
    amplitude: float = Field(default=1.0, gt=0)
    wavelength: float = Field(default=2.0, gt=0.1)
    cycles: float = Field(default=2.0, gt=0.5, le=8.0)
    annotate: bool = True
    region: str = "stage"


@component(version=1, domain="physics", params=WaveParams)
def wave_form(p: WaveParams) -> Built:
    """A sine wave with wavelength and amplitude marked."""
    from manim import Axes, DoubleArrow, MathTex, VGroup

    span = p.wavelength * p.cycles
    axes = Axes(
        x_range=[0, span, p.wavelength],
        y_range=[-p.amplitude * 1.6, p.amplitude * 1.6, p.amplitude],
        x_length=8.6, y_length=3.4, tips=False,
        axis_config={"include_numbers": True, "color": "#9aa7bd", "font_size": 20},
    )
    wave = axes.plot(
        lambda x: p.amplitude * math.sin(2 * math.pi * x / p.wavelength), x_range=[0, span], color=BODY_COLOR
    )
    parts = {"axes": axes, "wave": wave}
    group = VGroup(axes, wave)
    beats = [["axes"], ["wave"]]

    if p.annotate:
        crest = p.wavelength / 4
        lam = DoubleArrow(
            axes.c2p(crest, p.amplitude * 1.32), axes.c2p(crest + p.wavelength, p.amplitude * 1.32),
            buff=0, stroke_width=3, tip_length=0.16, color="#fbbf24",
        )
        amp = DoubleArrow(
            axes.c2p(crest, 0), axes.c2p(crest, p.amplitude), buff=0, stroke_width=3, tip_length=0.16, color="#4ade80"
        )
        parts.update({"wavelength_arrow": lam, "amplitude_arrow": amp})
        group.add(lam, amp)
        beats.append(["wavelength_arrow", "amplitude_arrow"])

        placed = []
        for key, tex, arrow in (("wavelength_label", r"\lambda", lam), ("amplitude_label", "A", amp)):
            text = MathTex(tex, font_size=27, color=arrow.get_color())
            result = place_label(text, arrow.get_center(), avoid=[axes, wave, lam, amp], placed=placed)
            parts[key] = text
            group.add(text)
            beats[-1].append(key)
            placed.append(text)
            if result["leader"] is not None:
                parts[f"{key}_leader"] = result["leader"]
                group.add(result["leader"])

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"lambda {p.wavelength}, amplitude {p.amplitude}")
