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
from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.collision import holds_text
from proofmotion.layout.labels import place_label
from proofmotion.layout.notation import to_latex
from proofmotion.layout.regions import layout, place

GRAVITY = 9.81
#: Longest force arrow, in scene units. Everything scales relative to this so a
#: 500 N force and a 5 N force stay on screen together.
MAX_ARROW = 1.7
BODY_COLOR = "#4aa3df"
FORCE_COLORS = ("#f87171", "#4ade80", "#fbbf24", "#a78bfa", "#38bdf8", "#fb923c")


def _latex_label(value: str) -> str:
    """Normalise Unicode maths copied from a prompt into LaTeX source.

    Delegates to the one table. This carried its own list of a dozen Greek
    letters and knew nothing about the operators or the superscripts, so the
    same class of bug was fixed here and still live everywhere else.
    """
    return to_latex(value)


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
        text = MathTex(_latex_label(force.label), font_size=26, color=arrow.get_color())
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
    body_text = MathTex(_latex_label(p.body), font_size=26)
    if p.shape == "dot":
        # A dot has no interior to write in, so the label sits beside it.
        place_label(body_text, origin, avoid=[body, *arrows.values()])
    else:
        # Written inside the body on purpose, which the checker has to be told:
        # a filled shape's interior counts as ink, and it cannot tell a mass
        # label in its own box from a stray label dropped on a figure.
        holds_text(body)
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
        angle_text = MathTex(_latex_label(p.label_angle), font_size=26, color="#fbbf24")
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


class LinearDragProjectileParams(BaseModel):
    mass_kg: float = Field(default=0.2, gt=0)
    drag_coefficient: float = Field(default=0.1, gt=0, description="Linear-drag coefficient c in kg/s.")
    speed: float = Field(default=270.0, gt=0)
    angle_deg: float = Field(default=60.0, gt=0, lt=90)
    wall_time: float = Field(default=2.0, gt=0)
    gravity: float = Field(default=GRAVITY, gt=0)
    e_approx: float | None = Field(default=None, gt=0, description="Use only when the question supplies an approximation for e.")
    region: str = "stage"


@component(version=1, domain="physics", params=LinearDragProjectileParams)
def linear_drag_projectile(p: LinearDragProjectileParams) -> Built:
    """Exact F=-cv trajectory, with its wall position marked at a chosen time."""
    import numpy as np
    from manim import Axes, DashedLine, Dot, Line, MathTex, VGroup

    beta = p.drag_coefficient / p.mass_kg
    theta = math.radians(p.angle_deg)
    ux, uy = p.speed * math.cos(theta), p.speed * math.sin(theta)

    def position(time: float) -> tuple[float, float]:
        decay = math.exp(-beta * time) if p.e_approx is None else p.e_approx ** (-beta * time)
        x = ux * (1 - decay) / beta
        y = (uy + p.gravity / beta) * (1 - decay) / beta - p.gravity * time / beta
        return x, y

    x_wall, y_wall = position(p.wall_time)
    samples = [position(p.wall_time * index / 100) for index in range(101)]
    max_y = max(y for _, y in samples)
    axes = Axes(
        x_range=[0, x_wall * 1.14, max(x_wall / 4, 1)], y_range=[0, max_y * 1.22, max(max_y / 3, 1)],
        x_length=8.2, y_length=3.9, tips=False,
        axis_config={"include_numbers": True, "color": "#9aa7bd", "font_size": 18},
    )
    trajectory = VGroup(*[
        Line(axes.c2p(*samples[index]), axes.c2p(*samples[index + 1]), color="#fbbf24", stroke_width=4)
        for index in range(len(samples) - 1)
    ])
    projectile = Dot(axes.c2p(x_wall, y_wall), radius=0.09, color=BODY_COLOR)
    wall = Line(axes.c2p(x_wall, 0), axes.c2p(x_wall, max_y * 1.1), color="#f87171", stroke_width=6)
    hit_guide = DashedLine(axes.c2p(x_wall, 0), axes.c2p(x_wall, y_wall), color="#94a3b8", stroke_width=2)
    labels = VGroup(
        MathTex(r"\vec F_d=-c\vec v", font_size=25, color="#f87171").next_to(axes, np.array([0.0, 1.0, 0.0]), buff=0.18),
        MathTex(rf"\frac{{c}}{{m}}={beta:g}\,\mathrm{{s^{{-1}}}}", font_size=22).next_to(axes, np.array([1.0, 0.0, 0.0]), buff=0.24),
        MathTex(rf"t={p.wall_time:g}\,\mathrm{{s}}", font_size=22).next_to(projectile, np.array([0.0, 1.0, 0.0]), buff=0.12),
        MathTex(rf"x={x_wall:.0f}\,\mathrm{{m}}", font_size=25, color="#4ade80").next_to(axes.c2p(x_wall, 0), np.array([0.0, -1.0, 0.0]), buff=0.18),
    )
    parts: dict[str, object] = {"axes": axes, "trajectory": trajectory, "wall": wall, "hit_guide": hit_guide, "projectile": projectile, "labels": labels}
    group = VGroup(axes, trajectory, wall, hit_guide, projectile, labels)
    beats = [["axes", "wall"], ["trajectory"], ["hit_guide", "projectile"], ["labels"]]
    place(group, layout("title_stage_caption")[p.region])
    approximation = f" using e={p.e_approx:g}" if p.e_approx is not None else " exactly"
    return Built(group=group, parts=parts, beats=beats, notes=f"linear drag c/m={beta:g}/s; wall at t={p.wall_time:g}s is x={x_wall:.6f}m, y={y_wall:.6f}m{approximation}")


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


class BusBrakingParams(BaseModel):
    initial_speed_kmh: float = Field(default=72.0, gt=0, description="Bus speed before braking, in km/h.")
    stopping_time: float = Field(default=4.0, gt=0, description="Time to rest, in seconds.")
    bus_color: str = Field(default="#fbbf24", description="Hex colour for the bus body.")
    show_velocity: bool = True
    region: str = "stage"


@component(version=1, domain="physics", params=BusBrakingParams)
def bus_braking_road(p: BusBrakingParams) -> Built:
    """A clearly recognisable 2D bus on a road for uniform-braking problems."""
    from manim import DOWN, LEFT, RIGHT, UP, WHITE, Arrow, Circle, Line, MathTex, Rectangle, RoundedRectangle, VGroup

    road = Rectangle(width=10.6, height=1.9, color="#64748b", fill_opacity=0.65, stroke_width=2)
    road.shift(DOWN * 1.65)
    dashes = VGroup(*[
        Line([x, -1.65, 0], [x + 0.65, -1.65, 0], color=WHITE, stroke_width=5)
        for x in (-4.8, -3.1, -1.4, 0.3, 2.0, 3.7)
    ])

    body = RoundedRectangle(width=3.25, height=1.15, corner_radius=0.15,
                            color=p.bus_color, fill_opacity=1, stroke_width=3)
    body.move_to(LEFT * 1.3 + DOWN * 0.75)
    roof = RoundedRectangle(width=1.75, height=0.63, corner_radius=0.13,
                            color=p.bus_color, fill_opacity=1, stroke_width=3)
    roof.next_to(body, UP, buff=-0.05).shift(LEFT * 0.15)
    windows = VGroup(*[
        Rectangle(width=0.43, height=0.36, color="#38bdf8", fill_opacity=0.9, stroke_width=1)
        for _ in range(4)
    ]).arrange(RIGHT, buff=0.12).move_to(roof.get_center() + DOWN * 0.03)
    door = Rectangle(width=0.35, height=0.72, color="#0f172a", fill_opacity=0.8, stroke_width=1)
    door.move_to(body.get_right() + LEFT * 0.34 + DOWN * 0.05)
    wheels = VGroup(*[
        Circle(radius=0.26, color="#111827", fill_opacity=1, stroke_width=2)
        for _ in range(2)
    ])
    wheels[0].move_to(body.get_left() + RIGHT * 0.65 + DOWN * 0.62)
    wheels[1].move_to(body.get_right() + LEFT * 0.65 + DOWN * 0.62)
    hubs = VGroup(*[Circle(radius=0.09, color="#cbd5e1", fill_opacity=1) for _ in range(2)])
    for hub, wheel in zip(hubs, wheels, strict=True):
        hub.move_to(wheel)
    bus = VGroup(body, roof, windows, door, wheels, hubs)

    speed_ms = p.initial_speed_kmh / 3.6
    speed_arrow = Arrow(bus.get_top() + RIGHT * 0.2, bus.get_top() + RIGHT * 2.2,
                        buff=0.1, color="#4ade80", stroke_width=4)
    speed_label = MathTex(rf"v_0={p.initial_speed_kmh:g}\,\mathrm{{km/h}}={speed_ms:g}\,\mathrm{{m/s}}",
                          font_size=26, color="#4ade80").next_to(speed_arrow, UP, buff=0.12)
    brake_label = MathTex(rf"\text{{uniform braking for }}{p.stopping_time:g}\,\mathrm{{s}}",
                          font_size=25, color="#f87171").next_to(road, DOWN, buff=0.18)

    parts: dict[str, object] = {"road": road, "lane_marks": dashes, "bus": bus, "brake_label": brake_label}
    group = VGroup(road, dashes, bus, brake_label)
    beats = [["road", "lane_marks"], ["bus"], ["brake_label"]]
    if p.show_velocity:
        parts.update({"velocity_arrow": speed_arrow, "velocity_label": speed_label})
        group.add(speed_arrow, speed_label)
        beats.append(["velocity_arrow", "velocity_label"])

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"2D bus braking from {p.initial_speed_kmh:g} km/h for {p.stopping_time:g} s")


class PowerTransmissionParams(BaseModel):
    power_kw: float = Field(default=600.0, gt=0, description="Power supplied, in kW.")
    plant_voltage: float = Field(default=4000.0, gt=0, description="Plant-side RMS voltage, in V.")
    step_up_ratio: float = Field(default=10.0, gt=1, description="Step-up secondary/primary turns ratio.")
    consumer_voltage: float = Field(default=200.0, gt=0, description="Required consumer RMS voltage, in V.")
    distance_km: float = Field(default=20.0, gt=0, description="Transmission distance, in km.")
    region: str = "stage"


@component(version=1, domain="physics", params=PowerTransmissionParams)
def power_transmission_diagram(p: PowerTransmissionParams) -> Built:
    """A labelled plant → step-up → high-voltage line → step-down → homes diagram."""
    from manim import DOWN, LEFT, RIGHT, UP, Circle, Line, MathTex, Rectangle, RoundedRectangle, Text, VGroup

    power_w = p.power_kw * 1000
    line_voltage = p.plant_voltage * p.step_up_ratio
    plant_current = power_w / p.plant_voltage
    line_current = power_w / line_voltage
    step_down_ratio = line_voltage / p.consumer_voltage

    plant = VGroup(
        Rectangle(width=1.25, height=1.15, color="#475569", fill_opacity=0.9),
        Rectangle(width=0.22, height=0.7, color="#64748b", fill_opacity=1).shift(LEFT * 0.32 + UP * 0.9),
        Rectangle(width=0.22, height=0.95, color="#64748b", fill_opacity=1).shift(RIGHT * 0.32 + UP * 1.03),
        Text("POWER\nPLANT", font_size=17, color="#f8fafc"),
    ).move_to(LEFT * 5.0 + DOWN * 0.15)

    def transformer(name: str, colour: str):
        core = RoundedRectangle(width=1.05, height=1.35, corner_radius=0.12, color=colour, fill_opacity=0.25, stroke_width=3)
        coils = VGroup(*[Circle(radius=0.17, color=colour, stroke_width=3) for _ in range(3)])
        coils.arrange(DOWN, buff=0.05).shift(LEFT * 0.23)
        coils_2 = coils.copy().shift(RIGHT * 0.46)
        label = Text(name, font_size=15, color=colour).next_to(core, DOWN, buff=0.12)
        return VGroup(core, coils, coils_2, label)

    step_up = transformer("STEP-UP", "#fbbf24").move_to(LEFT * 2.55 + DOWN * 0.15)
    step_down = transformer("STEP-DOWN", "#4ade80").move_to(RIGHT * 2.55 + DOWN * 0.15)
    houses = VGroup()
    for shift in (RIGHT * 4.65, RIGHT * 5.45):
        base = Rectangle(width=0.62, height=0.5, color="#38bdf8", fill_opacity=0.75)
        roof = Line(base.get_left() + UP * 0.25, base.get_center() + UP * 0.72, color="#f87171", stroke_width=5)
        roof_2 = Line(base.get_center() + UP * 0.72, base.get_right() + UP * 0.25, color="#f87171", stroke_width=5)
        houses.add(VGroup(base, roof, roof_2).move_to(shift + DOWN * 0.28))
    homes_label = Text("CONSUMERS", font_size=16, color="#e2e8f0").next_to(houses, DOWN, buff=0.15)
    homes = VGroup(houses, homes_label)

    low_line = Line(plant.get_right() + RIGHT * 0.05, step_up.get_left() + LEFT * 0.08, color="#38bdf8", stroke_width=4)
    high_line = Line(step_up.get_right() + RIGHT * 0.05, step_down.get_left() + LEFT * 0.05, color="#f87171", stroke_width=6)
    output_line = Line(step_down.get_right() + RIGHT * 0.05, homes.get_left() + LEFT * 0.08, color="#4ade80", stroke_width=4)
    towers = VGroup(*[
        VGroup(Line([x, -0.68, 0], [x, 1.2, 0], color="#94a3b8", stroke_width=3),
               Line([x - 0.26, 0.77, 0], [x + 0.26, 0.77, 0], color="#94a3b8", stroke_width=2))
        for x in (-0.75, 0.75)
    ])

    labels = VGroup(
        MathTex(rf"P={p.power_kw:g}\,\mathrm{{kW}}", font_size=24).next_to(plant, UP, buff=0.12),
        MathTex(rf"V_p={p.plant_voltage:g}\,\mathrm{{V}},\ I_p={plant_current:g}\,\mathrm{{A}}", font_size=21, color="#38bdf8").next_to(low_line, UP, buff=0.14),
        MathTex(rf"V_{{\rm line}}={line_voltage:g}\,\mathrm{{V}},\ I_{{\rm line}}={line_current:g}\,\mathrm{{A}}", font_size=21, color="#f87171").next_to(high_line, UP, buff=0.3),
        MathTex(rf"{p.distance_km:g}\,\mathrm{{km}}", font_size=20, color="#e2e8f0").next_to(high_line, DOWN, buff=0.34),
        MathTex(rf"V_s={p.consumer_voltage:g}\,\mathrm{{V}}", font_size=21, color="#4ade80").next_to(output_line, DOWN, buff=0.14),
        MathTex(rf"\frac{{N_p}}{{N_s}}=\frac{{{line_voltage:g}}}{{{p.consumer_voltage:g}}}={step_down_ratio:g}:1", font_size=25, color="#fbbf24").move_to(DOWN * 2.2),
    )
    parts: dict[str, object] = {
        "power_plant": plant, "step_up_transformer": step_up, "high_voltage_line": high_line,
        "transmission_towers": towers, "step_down_transformer": step_down, "consumers": homes,
        "plant_line": low_line, "consumer_line": output_line, "labels": labels,
    }
    group = VGroup(*parts.values())
    beats = [["power_plant", "step_up_transformer", "plant_line"], ["high_voltage_line", "transmission_towers"], ["step_down_transformer", "consumers", "consumer_line"], ["labels"]]
    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=(f"ideal transmission: {p.plant_voltage:g} V -> {line_voltage:g} V; "
               f"current {plant_current:g} A -> {line_current:g} A; step-down ratio {step_down_ratio:g}:1"),
    )


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

    # A wave that does not travel is a picture of a sine curve. Redrawing the
    # phase rather than sliding the mobject keeps it inside its own axes:
    # shifting would carry the crest off the end of the plot.
    def travel() -> Any:
        from manim import UpdateFromAlphaFunc

        def at_phase(target: Any, alpha: float) -> None:
            shifted = axes.plot(
                lambda x: p.amplitude * math.sin(
                    2 * math.pi * (x - alpha * p.wavelength) / p.wavelength
                ),
                x_range=[0, span], color=BODY_COLOR,
            )
            target.become(shifted)

        return UpdateFromAlphaFunc(wave, at_phase)

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
    return Built(group=group, parts=parts, beats=beats, motions=[travel],
                 notes=f"lambda {p.wavelength}, amplitude {p.amplitude}")


class MeterScaleFrictionParams(BaseModel):
    left_cm: float = Field(default=18.0, ge=0, le=100)
    right_cm: float = Field(default=75.6, ge=0, le=100)
    static_friction: float = Field(default=0.40, gt=0)
    dynamic_friction: float = Field(default=0.32, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=MeterScaleFrictionParams)
def meter_scale_friction(p: MeterScaleFrictionParams) -> Built:
    """Uniform metre scale on two fingers, labelled with reactions and alternating-slip positions."""
    from manim import DOWN, RIGHT, UP, Arrow, Line, MathTex, Rectangle, Text, VGroup

    scale = Rectangle(width=9.5, height=0.36, color="#e2e8f0", fill_opacity=0.9, stroke_width=2)
    ticks = VGroup(*[Line(scale.get_left() + RIGHT * (9.5 * i / 10), scale.get_left() + RIGHT * (9.5 * i / 10) + DOWN * (0.12 if i % 5 else 0.22), color="#475569", stroke_width=2) for i in range(11)])
    center = scale.get_left() + RIGHT * 4.75
    def x_to_point(value: float):
        return scale.get_left() + RIGHT * (9.5 * value / 100)
    def finger(value: float, colour: str, label: str):
        tip = x_to_point(value) + DOWN * 0.18
        hand = VGroup(Line(tip + DOWN * 1.05, tip, color=colour, stroke_width=12), Circle(radius=0.16, color=colour, fill_opacity=1).move_to(tip + DOWN * 1.0))
        arrow = Arrow(tip + DOWN * 0.78, tip + UP * 0.05, buff=0, color=colour, stroke_width=3)
        return VGroup(hand, arrow, MathTex(label, font_size=24, color=colour).next_to(hand, DOWN, buff=0.18))
    from manim import Circle
    left = finger(p.left_cm, "#38bdf8", r"N_L")
    right = finger(p.right_cm, "#f87171", r"N_R")
    center_mark = Line(center + UP * 0.35, center + DOWN * 0.45, color="#fbbf24", stroke_width=3)
    labels = VGroup(
        Text("0 cm", font_size=18, color="#334155").next_to(scale.get_left(), UP, buff=0.28),
        Text("50 cm", font_size=18, color="#fbbf24").next_to(center_mark, UP, buff=0.28),
        Text("100 cm", font_size=18, color="#334155").next_to(scale.get_right(), UP, buff=0.28),
        MathTex(rf"x_R={p.right_cm-50:g}\,\mathrm{{cm}}", font_size=28, color="#fbbf24").next_to(right, RIGHT, buff=0.25),
        MathTex(rf"\mu_s={p.static_friction:g},\ \mu_k={p.dynamic_friction:g}", font_size=25).move_to(DOWN * 2.25),
    )
    parts: dict[str, object] = {"meter_scale": scale, "ticks": ticks, "left_finger": left, "right_finger": right, "center_mark": center_mark, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["meter_scale", "ticks", "center_mark"], ["left_finger", "right_finger"], ["labels"]], notes="alternating slip: sliding finger has dynamic friction, fixed finger reaches limiting static friction")
