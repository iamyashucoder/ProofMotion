"""Oscillations, collisions, orbits and rotation.

Each computes the physics it displays — period, momentum, orbital speed, torque —
so the numbers on screen come from the parameters rather than from a caption
someone typed.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.labels import place_label
from proofmotion.layout.regions import layout, place

GRAVITY = 9.81
BODY = "#4aa3df"
FORCE = "#f87171"
ACCENT = "#4ade80"
HIGHLIGHT = "#fbbf24"


def _annotate(anchor, tex: str, avoid: list, placed: list, parts: dict, group, row: list, key: str, colour=None):
    """Place one label with the scorer and record it under `key`."""
    from manim import MathTex

    text = MathTex(tex, font_size=25, color=colour) if colour else MathTex(tex, font_size=25)
    result = place_label(text, anchor, avoid=avoid, placed=placed)
    parts[key] = text
    placed.append(text)
    group.add(text)
    row.append(key)
    if result["leader"] is not None:
        parts[f"{key}_leader"] = result["leader"]
        group.add(result["leader"])


class PendulumParams(BaseModel):
    length: float = Field(default=1.0, gt=0, description="Length in metres; sets the period.")
    angle_deg: float = Field(default=25.0, gt=0, lt=90, description="Displacement from vertical.")
    show_forces: bool = True
    region: str = "stage"


@component(version=1, domain="physics", params=PendulumParams)
def pendulum(p: PendulumParams) -> Built:
    """A pendulum at a displacement, with its small-angle period computed.

    The period shown is 2*pi*sqrt(L/g), and the note records how far the
    small-angle approximation is from the truth at this amplitude — which is the
    assumption most pendulum explanations leave unstated.
    """
    import numpy as np
    from manim import Angle, Arrow, Circle, DashedLine, Line, VGroup

    radians = math.radians(p.angle_deg)
    arm = 2.6
    pivot = np.array([0.0, 1.6, 0.0])
    bob_at = pivot + np.array([arm * math.sin(radians), -arm * math.cos(radians), 0.0])
    rest_at = pivot + np.array([0.0, -arm, 0.0])

    rod = Line(pivot, bob_at, color="#94a3b8", stroke_width=3)
    vertical = DashedLine(pivot, rest_at, color="#475569", stroke_width=2)
    bob = Circle(radius=0.26, color=BODY, fill_opacity=0.55).move_to(bob_at)
    hinge = Circle(radius=0.06, color="#94a3b8", fill_opacity=1).move_to(pivot)
    arc = Angle(Line(pivot, rest_at), rod, radius=0.6, color=HIGHLIGHT)

    parts: dict[str, Any] = {"rod": rod, "vertical": vertical, "bob": bob, "pivot": hinge, "angle": arc}
    group = VGroup(vertical, rod, arc, hinge, bob)
    beats = [["pivot", "vertical"], ["rod", "bob", "angle"]]
    obstacles = [rod, vertical, bob, arc]

    row: list[str] = []
    if p.show_forces:
        weight = Arrow(bob_at, bob_at + np.array([0, -1.05, 0]), buff=0, stroke_width=4, color=FORCE)
        along = (pivot - bob_at) / np.linalg.norm(pivot - bob_at)
        tension = Arrow(bob_at, bob_at + along * 0.95, buff=0, stroke_width=4, color=ACCENT)
        parts.update({"weight": weight, "tension": tension})
        group.add(weight, tension)
        obstacles += [weight, tension]
        row += ["weight", "tension"]
    if row:
        beats.append(row)

    period = 2 * math.pi * math.sqrt(p.length / GRAVITY)
    # First correction to the small-angle period: T(1 + theta^2/16 + ...)
    correction = 1 + radians**2 / 16
    placed: list[Any] = []
    labels: list[str] = []
    if p.show_forces:
        _annotate(parts["weight"].get_end(), "mg", obstacles, placed, parts, group, labels, "weight_label", FORCE)
        _annotate(parts["tension"].get_end(), "T", obstacles, placed, parts, group, labels, "tension_label", ACCENT)
    _annotate(pivot + np.array([0.35, -0.85, 0.0]), rf"\theta={p.angle_deg:g}^\circ",
              obstacles, placed, parts, group, labels, "angle_label", HIGHLIGHT)
    _annotate(np.array([0.0, -2.3, 0.0]), rf"T=2\pi\sqrt{{L/g}}={period:.3f}\,\text{{s}}",
              obstacles, placed, parts, group, labels, "period_label")
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])

    # A pendulum that does not swing is a diagram of a pendulum. It rotates
    # about its own pivot, through twice the displacement and back, so what is
    # animated is the amplitude the parameters actually describe.
    #
    # The angle mark and the force arrows are left out of the rotation and
    # faded for its duration. Carrying them round would be worse than not
    # moving at all: the weight arrow would stop pointing down, and an arrow
    # labelled mg that does not point down is a lie about the physics. They
    # belong to the displaced position the rest of the figure describes.
    swinging = VGroup(rod, bob)
    attached = VGroup(*[
        parts[name] for name in
        ("angle", "angle_label", "tension", "tension_label", "weight", "weight_label")
        if name in parts
    ])
    turn = -2 * radians

    def swing() -> Any:
        from manim import FadeIn, FadeOut, Rotate, Succession

        steps = [
            Rotate(swinging, angle=turn, about_point=pivot),
            Rotate(swinging, angle=-turn, about_point=pivot),
        ]
        if len(attached):
            steps = [FadeOut(attached), *steps, FadeIn(attached)]
        return Succession(*steps)

    return Built(
        group=group, parts=parts, beats=beats, motions=[swing],
        notes=(
            f"small-angle period {period:.6f} s; at {p.angle_deg:g} deg the true period is about "
            f"{correction:.4f} times that, so the approximation is off by {(correction - 1) * 100:.2f}%"
        ),
    )


class SpringMassParams(BaseModel):
    mass: float = Field(default=1.0, gt=0, description="Mass in kg.")
    stiffness: float = Field(default=10.0, gt=0, description="Spring constant in N/m.")
    displacement: float = Field(default=1.0, description="Extension from equilibrium, in scene units.")
    region: str = "stage"


@component(version=1, domain="physics", params=SpringMassParams)
def spring_mass(p: SpringMassParams) -> Built:
    """A mass on a spring, with angular frequency and period computed."""
    import numpy as np
    from manim import DashedLine, Line, Rectangle, VGroup

    wall_x, rest_x = -4.2, -0.6
    mass_x = rest_x + max(-2.6, min(2.6, p.displacement))
    wall = Line(np.array([wall_x, -1.1, 0]), np.array([wall_x, 1.1, 0]), stroke_width=6, color="#64748b")
    coils, span = 14, mass_x - wall_x
    points = [np.array([wall_x, 0.0, 0.0])]
    for i in range(1, coils):
        points.append(np.array([wall_x + span * i / coils, 0.28 * (1 if i % 2 else -1), 0.0]))
    points.append(np.array([mass_x, 0.0, 0.0]))
    spring = VGroup(*[Line(points[i], points[i + 1], stroke_width=3, color="#94a3b8") for i in range(len(points) - 1)])
    block = Rectangle(width=0.9, height=0.9, color=BODY, fill_opacity=0.45).move_to(np.array([mass_x + 0.45, 0, 0]))
    equilibrium = DashedLine(np.array([rest_x + 0.45, -1.2, 0]), np.array([rest_x + 0.45, 1.2, 0]),
                             stroke_width=2, color="#475569")

    omega = math.sqrt(p.stiffness / p.mass)
    period = 2 * math.pi / omega
    energy = 0.5 * p.stiffness * p.displacement**2

    parts: dict[str, Any] = {"wall": wall, "spring": spring, "block": block, "equilibrium": equilibrium}
    group = VGroup(wall, equilibrium, spring, block)
    beats = [["wall", "equilibrium"], ["spring", "block"]]

    obstacles = [wall, spring, block, equilibrium]
    placed: list[Any] = []
    labels: list[str] = []
    _annotate(block.get_center(), "m", obstacles, placed, parts, group, labels, "mass_label")
    _annotate(np.array([(wall_x + mass_x) / 2, 0.45, 0.0]), rf"k={p.stiffness:g}",
              obstacles, placed, parts, group, labels, "k_label", HIGHLIGHT)
    _annotate(np.array([0.0, -1.9, 0.0]),
              rf"\omega=\sqrt{{k/m}}={omega:.3f},\ T={period:.3f}\,\text{{s}}",
              obstacles, placed, parts, group, labels, "period_label")
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])

    # The mass travels to the far side of rest and back, which is the
    # oscillation the period underneath describes. The spring is stretched
    # with it so the coils do not detach from the block.
    travel = (rest_x - mass_x) * 2

    def oscillate() -> Any:
        from manim import RIGHT, Succession

        moving = VGroup(spring, block, *[m for k, m in parts.items() if k == "mass_label"])
        return Succession(
            moving.animate.shift(RIGHT * travel).build(),
            moving.animate.shift(RIGHT * -travel).build(),
        )

    return Built(group=group, parts=parts, beats=beats, motions=[oscillate],
                 notes=f"omega={omega:.6f} rad/s, T={period:.6f} s, stored energy {energy:.4f} J at this extension")


class CollisionParams(BaseModel):
    mass_a: float = Field(default=1.0, gt=0)
    mass_b: float = Field(default=1.0, gt=0)
    velocity_a: float = Field(default=3.0)
    velocity_b: float = Field(default=-1.0)
    kind: Literal["elastic", "inelastic"] = "elastic"
    region: str = "stage"


@component(version=1, domain="physics", params=CollisionParams)
def collision(p: CollisionParams) -> Built:
    """Two bodies before and after a collision, with the outcome solved for.

    Final velocities come from conservation, not from the caller — so the arrows
    and the algebra cannot disagree.
    """
    import numpy as np
    from manim import Arrow, Circle, DashedLine, Line, VGroup

    total_p = p.mass_a * p.velocity_a + p.mass_b * p.velocity_b
    if p.kind == "elastic":
        total = p.mass_a + p.mass_b
        final_a = ((p.mass_a - p.mass_b) * p.velocity_a + 2 * p.mass_b * p.velocity_b) / total
        final_b = ((p.mass_b - p.mass_a) * p.velocity_b + 2 * p.mass_a * p.velocity_a) / total
    else:
        final_a = final_b = total_p / (p.mass_a + p.mass_b)

    ke_before = 0.5 * p.mass_a * p.velocity_a**2 + 0.5 * p.mass_b * p.velocity_b**2
    ke_after = 0.5 * p.mass_a * final_a**2 + 0.5 * p.mass_b * final_b**2

    floor = Line(np.array([-5.2, -1.4, 0]), np.array([5.2, -1.4, 0]), stroke_width=3, color="#475569")
    divider = DashedLine(np.array([0, -1.4, 0]), np.array([0, 1.9, 0]), stroke_width=2, color="#334155")
    radius_a = 0.32 * (p.mass_a ** (1 / 3))
    radius_b = 0.32 * (p.mass_b ** (1 / 3))
    before_a = Circle(radius=radius_a, color=BODY, fill_opacity=0.5).move_to(np.array([-4.0, -1.4 + radius_a, 0]))
    before_b = Circle(radius=radius_b, color=FORCE, fill_opacity=0.5).move_to(np.array([-1.4, -1.4 + radius_b, 0]))
    after_a = Circle(radius=radius_a, color=BODY, fill_opacity=0.5).move_to(np.array([1.4, -1.4 + radius_a, 0]))
    after_b = Circle(radius=radius_b, color=FORCE, fill_opacity=0.5).move_to(np.array([4.0, -1.4 + radius_b, 0]))

    def arrow_for(circle, speed, colour):
        scale = 0.42
        length = max(0.28, min(1.4, abs(speed) * scale))
        direction = 1.0 if speed >= 0 else -1.0
        start = circle.get_center() + np.array([0, 0.55, 0])
        return Arrow(start, start + np.array([direction * length, 0, 0]), buff=0, stroke_width=4, color=colour)

    arrows = {
        "v_a_before": arrow_for(before_a, p.velocity_a, BODY),
        "v_b_before": arrow_for(before_b, p.velocity_b, FORCE),
        "v_a_after": arrow_for(after_a, final_a, BODY),
        "v_b_after": arrow_for(after_b, final_b, FORCE),
    }

    parts: dict[str, Any] = {
        "floor": floor, "divider": divider,
        "before_a": before_a, "before_b": before_b, "after_a": after_a, "after_b": after_b, **arrows,
    }
    group = VGroup(floor, divider, before_a, before_b, after_a, after_b, *arrows.values())
    beats = [["floor", "divider"], ["before_a", "before_b", "v_a_before", "v_b_before"],
             ["after_a", "after_b", "v_a_after", "v_b_after"]]

    obstacles = [floor, divider, before_a, before_b, after_a, after_b, *arrows.values()]
    placed: list[Any] = []
    labels: list[str] = []
    for key, circle, value, colour in (
        ("before_a_label", before_a, p.velocity_a, BODY), ("before_b_label", before_b, p.velocity_b, FORCE),
        ("after_a_label", after_a, final_a, BODY), ("after_b_label", after_b, final_b, FORCE),
    ):
        _annotate(circle.get_center(), f"{value:.2f}", obstacles, placed, parts, group, labels, key, colour)
    _annotate(np.array([0.0, 2.3, 0.0]), rf"p={total_p:.3f}\ \text{{conserved}}",
              obstacles, placed, parts, group, labels, "momentum_label", HIGHLIGHT)
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=(
            f"{p.kind}: v_a {p.velocity_a:g} -> {final_a:.6f}, v_b {p.velocity_b:g} -> {final_b:.6f}; "
            f"momentum {total_p:.6f} conserved; KE {ke_before:.6f} -> {ke_after:.6f}"
        ),
    )


class OrbitParams(BaseModel):
    semi_major: float = Field(default=2.4, gt=0.4, le=3.2, description="Semi-major axis in scene units.")
    eccentricity: float = Field(default=0.5, ge=0.0, lt=0.95)
    body_angle_deg: float = Field(default=40.0, description="Where the orbiting body sits, from perihelion.")
    region: str = "stage"


@component(version=1, domain="physics", params=OrbitParams)
def orbit(p: OrbitParams) -> Built:
    """An elliptical orbit with the focus, apsides and swept radius.

    Kepler's first law drawn correctly: the primary sits at a focus, not the
    centre, which is the detail hand-drawn orbit diagrams usually get wrong.
    """
    import numpy as np
    from manim import Dot, Ellipse, Line, VGroup

    a = p.semi_major
    b = a * math.sqrt(1 - p.eccentricity**2)
    c = a * p.eccentricity

    path = Ellipse(width=2 * a, height=2 * b, color="#64748b", stroke_width=3)
    primary = Dot(np.array([-c, 0.0, 0.0]), radius=0.16, color=HIGHLIGHT)
    centre = Dot(np.array([0.0, 0.0, 0.0]), radius=0.045, color="#475569")
    theta = math.radians(p.body_angle_deg)
    position = np.array([a * math.cos(theta), b * math.sin(theta), 0.0])
    body = Dot(position, radius=0.1, color=BODY)
    radius_line = Line(primary.get_center(), position, stroke_width=2, color="#94a3b8")
    perihelion = Dot(np.array([-a, 0.0, 0.0]), radius=0.06, color=ACCENT)
    aphelion = Dot(np.array([a, 0.0, 0.0]), radius=0.06, color=FORCE)

    parts: dict[str, Any] = {
        "path": path, "primary": primary, "centre": centre, "body": body,
        "radius": radius_line, "perihelion": perihelion, "aphelion": aphelion,
    }
    group = VGroup(path, centre, primary, perihelion, aphelion, radius_line, body)
    beats = [["path", "centre"], ["primary", "perihelion", "aphelion"], ["radius", "body"]]

    obstacles = [path, radius_line]
    placed: list[Any] = []
    labels: list[str] = []
    _annotate(primary.get_center(), r"\text{focus}", obstacles, placed, parts, group, labels, "focus_label", HIGHLIGHT)
    _annotate(perihelion.get_center(), rf"r_{{\min}}={a - c:.2f}", obstacles, placed, parts, group, labels,
              "perihelion_label", ACCENT)
    _annotate(aphelion.get_center(), rf"r_{{\max}}={a + c:.2f}", obstacles, placed, parts, group, labels,
              "aphelion_label", FORCE)
    _annotate(np.array([0.0, -b - 0.7, 0.0]), rf"e={p.eccentricity:g}",
              obstacles, placed, parts, group, labels, "eccentricity_label")
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(
        group=group, parts=parts, beats=beats,
        notes=(
            f"a={a:g}, b={b:.6f}, c={c:.6f}; perihelion {a - c:.6f}, aphelion {a + c:.6f}; "
            "the primary is at a focus, not the centre"
        ),
    )


class TorqueParams(BaseModel):
    lever_arm: float = Field(default=2.4, gt=0.3, le=4.0, description="Distance from the pivot.")
    force: float = Field(default=10.0, gt=0, description="Applied force in newtons.")
    angle_deg: float = Field(default=60.0, gt=0, le=180, description="Angle between the arm and the force.")
    region: str = "stage"


@component(version=1, domain="physics", params=TorqueParams)
def torque_diagram(p: TorqueParams) -> Built:
    """A lever with an applied force, and the torque r F sin(theta) computed.

    Shows the perpendicular component explicitly, which is the part that does
    the turning and the part most often conflated with the whole force.
    """
    import numpy as np
    from manim import Angle, Arrow, DashedLine, Dot, Line, VGroup

    pivot = np.array([-2.6, -0.4, 0.0])
    tip = pivot + np.array([p.lever_arm, 0.0, 0.0])
    radians = math.radians(p.angle_deg)
    magnitude = min(1.8, 0.13 * p.force + 0.4)
    force_vec = np.array([magnitude * math.cos(radians), magnitude * math.sin(radians), 0.0])

    arm = Line(pivot, tip, stroke_width=5, color="#94a3b8")
    hinge = Dot(pivot, radius=0.09, color=HIGHLIGHT)
    applied = Arrow(tip, tip + force_vec, buff=0, stroke_width=4, color=FORCE)
    perpendicular = Arrow(tip, tip + np.array([0.0, force_vec[1], 0.0]), buff=0, stroke_width=3, color=ACCENT)
    guide = DashedLine(tip + force_vec, tip + np.array([0.0, force_vec[1], 0.0]), stroke_width=1.6, color="#475569")
    arc = Angle(Line(tip, pivot), applied, radius=0.5, color=HIGHLIGHT) if 0.5 < p.angle_deg < 179.5 else None

    torque = p.lever_arm * p.force * math.sin(radians)
    parts: dict[str, Any] = {"arm": arm, "pivot": hinge, "force": applied,
                            "perpendicular": perpendicular, "guide": guide}
    group = VGroup(arm, hinge, applied, guide, perpendicular)
    beats = [["arm", "pivot"], ["force"], ["guide", "perpendicular"]]
    obstacles = [arm, applied, perpendicular, guide]
    if arc is not None:
        parts["angle"] = arc
        group.add(arc)
        beats[1].append("angle")
        obstacles.append(arc)

    placed: list[Any] = []
    labels: list[str] = []
    _annotate(applied.get_end(), "F", obstacles, placed, parts, group, labels, "force_label", FORCE)
    _annotate(perpendicular.get_end(), r"F\sin\theta", obstacles, placed, parts, group, labels, "perp_label", ACCENT)
    _annotate((pivot + tip) / 2, "r", obstacles, placed, parts, group, labels, "arm_label")
    _annotate(np.array([0.0, -2.2, 0.0]), rf"\tau=rF\sin\theta={torque:.3f}\,\text{{N·m}}",
              obstacles, placed, parts, group, labels, "torque_label", HIGHLIGHT)
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"torque {torque:.6f} N·m from r={p.lever_arm:g}, F={p.force:g}, theta={p.angle_deg:g} deg")


class StandingWaveParams(BaseModel):
    harmonic: int = Field(default=3, ge=1, le=8, description="Which harmonic; n antinodes.")
    length: float = Field(default=8.0, gt=1.0, description="String length in scene units.")
    amplitude: float = Field(default=1.0, gt=0)
    show_nodes: bool = True
    region: str = "stage"


@component(version=1, domain="physics", params=StandingWaveParams)
def standing_wave(p: StandingWaveParams) -> Built:
    """A standing wave with nodes marked and the wavelength derived from n.

    The relationship lambda = 2L/n is computed, so the picture and the formula
    agree by construction rather than by the author remembering.
    """
    import numpy as np
    from manim import Dot, Line, ParametricFunction, VGroup

    wavelength = 2 * p.length / p.harmonic
    axis = Line(np.array([-p.length / 2, 0, 0]), np.array([p.length / 2, 0, 0]), stroke_width=2, color="#475569")

    def shape(sign: float):
        return ParametricFunction(
            lambda t: np.array([t, sign * p.amplitude * math.sin(p.harmonic * math.pi * (t + p.length / 2) / p.length), 0.0]),
            t_range=[-p.length / 2, p.length / 2, p.length / 200],
            color=BODY if sign > 0 else "#64748b",
            stroke_opacity=1.0 if sign > 0 else 0.45,
        )

    crest, trough = shape(1.0), shape(-1.0)
    parts: dict[str, Any] = {"axis": axis, "crest": crest, "trough": trough}
    group = VGroup(axis, trough, crest)
    beats = [["axis"], ["crest", "trough"]]

    if p.show_nodes:
        nodes = VGroup(*[
            Dot(np.array([-p.length / 2 + i * p.length / p.harmonic, 0, 0]), radius=0.07, color=HIGHLIGHT)
            for i in range(p.harmonic + 1)
        ])
        parts["nodes"] = nodes
        group.add(nodes)
        beats.append(["nodes"])

    obstacles = [axis, crest, trough]
    placed: list[Any] = []
    labels: list[str] = []
    _annotate(np.array([0.0, p.amplitude + 0.55, 0.0]),
              rf"n={p.harmonic},\ \lambda=\frac{{2L}}{{n}}={wavelength:.3f}",
              obstacles, placed, parts, group, labels, "wavelength_label", HIGHLIGHT)
    beats.append(labels)

    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats,
                 notes=f"harmonic {p.harmonic}: lambda={wavelength:.6f}, {p.harmonic + 1} nodes, {p.harmonic} antinodes")
