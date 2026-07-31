"""Directable characters — a minimal stick-figure hero and the geometry that builds his world.

The library drew apparatus: axes, springs, circuits. A question that is a story
— someone doing something, somewhere — had nowhere to go, and the model
hand-built figures out of raw Lines, differently and badly, every time.

Two characters carry the story. Spyder Math is an original glowing stick
figure: human, minimal, a few mathematical tools — a web that is a line or a
catenary, a swing that is a pendulum arc, a leap that is a projectile
parabola. ProofMotion is not a creature: it is geometry that takes any form —
orb, swing line, ramp, spiral, arches, steps — and builds the environments the
hero moves through. math_scene stages the hero inside a world ProofMotion
built, and every traversal is a curve computed here, never taken on trust.
"""

from __future__ import annotations

import math
import random
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from proofmotion.components.base import Built, component
from proofmotion.components.palette import PALETTE
from proofmotion.layout.regions import layout, place


#: Rig segment lengths, in scene units at scale 1. The figure stands ~1.5 tall.
HEAD_R = 0.16
TORSO = 0.52
UPPER_ARM = 0.30
LOWER_ARM = 0.28
UPPER_LEG = 0.36
LOWER_LEG = 0.36

#: Named poses as joint angles, in degrees. Segment angles are measured from
#: straight down, positive toward the facing direction; elbow and knee are
#: bends added to the parent segment's angle; lean tilts the torso forward.
#: "f" is the leading side (toward the facing), "b" the trailing side.
POSES: dict[str, dict[str, float]] = {
    "stand": dict(lean=0, shoulder_f=14, elbow_f=8, shoulder_b=-14, elbow_b=-8,
                  hip_f=8, knee_f=-4, hip_b=-8, knee_b=4),
    "crouch": dict(lean=28, shoulder_f=42, elbow_f=48, shoulder_b=-18, elbow_b=-24,
                   hip_f=58, knee_f=-104, hip_b=-26, knee_b=44),
    "run_contact": dict(lean=16, shoulder_f=48, elbow_f=52, shoulder_b=-42, elbow_b=-40,
                        hip_f=28, knee_f=-14, hip_b=-38, knee_b=-28),
    "run_pass": dict(lean=12, shoulder_f=18, elbow_f=40, shoulder_b=-18, elbow_b=-30,
                     hip_f=6, knee_f=-16, hip_b=-10, knee_b=-52),
    "run_air": dict(lean=20, shoulder_f=56, elbow_f=48, shoulder_b=-50, elbow_b=-36,
                    hip_f=52, knee_f=-70, hip_b=-44, knee_b=-58),
    "swing": dict(lean=-12, shoulder_f=162, elbow_f=6, shoulder_b=148, elbow_b=10,
                  hip_f=30, knee_f=-52, hip_b=12, knee_b=-36),
    "cast": dict(lean=8, shoulder_f=126, elbow_f=18, shoulder_b=-32, elbow_b=-12,
                 hip_f=22, knee_f=-6, hip_b=-22, knee_b=6),
    "brace": dict(lean=-10, shoulder_f=64, elbow_f=74, shoulder_b=48, elbow_b=82,
                  hip_f=32, knee_f=-54, hip_b=-20, knee_b=28),
    "victory": dict(lean=0, shoulder_f=158, elbow_f=12, shoulder_b=-158, elbow_b=-12,
                    hip_f=10, knee_f=-4, hip_b=-10, knee_b=4),
    "defeated": dict(lean=38, shoulder_f=22, elbow_f=6, shoulder_b=12, elbow_b=6,
                     hip_f=78, knee_f=-118, hip_b=-20, knee_b=-130),
    # The playful ones: a dab tucks the face into the leading elbow while both
    # arms point the same way; a flail throws every limb wide, mid-air.
    "dab": dict(lean=6, shoulder_f=118, elbow_f=62, shoulder_b=152, elbow_b=8,
                hip_f=12, knee_f=-6, hip_b=-12, knee_b=6),
    "flail": dict(lean=-5, shoulder_f=120, elbow_f=-28, shoulder_b=-120, elbow_b=28,
                  hip_f=58, knee_f=24, hip_b=-58, knee_b=-24),
}


def _halo(mobject: Any, *, factor: float = 2.4, opacity: float = 0.10, colour: str | None = None) -> Any:
    """A single soft halo behind a stroke: the same geometry, wider and fainter."""
    halo = mobject.copy()
    for piece in halo.family_members_with_points():
        piece.set_fill(opacity=0.0)
        stroke: dict[str, Any] = {"width": float(piece.get_stroke_width()) * factor, "opacity": opacity}
        if colour:
            stroke["color"] = colour
        piece.set_stroke(**stroke)
    return halo


def _glowed(mobject: Any, *, colour: str | None = None) -> Any:
    """The stroke with its single halo behind it, as one group."""
    from manim import VGroup

    return VGroup(_halo(mobject, colour=colour), mobject)


def _stick_figure(
    pose: str, at: tuple[float, float] = (0.0, 0.0), scale: float = 1.0, facing: str = "right"
) -> tuple[Any, dict[str, Any]]:
    """The rig: head, torso, and two-segment limbs driven by a pose's joint angles.

    The lowest point of the pose is computed and set on y = 0 of the rig's
    local frame, so a grounded figure stands exactly on a surface drawn at the
    same height. Returns (group, joints) — joints are final scene points, so a
    web can anchor to "wrist_f" without re-deriving the arm.
    """
    import numpy as np
    from manim import Circle, Line, VGroup

    angles = POSES[pose]

    def ray(origin: Any, angle_deg: float, length: float) -> Any:
        a = math.radians(angle_deg)
        return origin + length * np.array([math.sin(a), -math.cos(a), 0.0])

    pelvis = np.array([0.0, 0.0, 0.0])
    lean = math.radians(angles["lean"])
    up = np.array([math.sin(lean), math.cos(lean), 0.0])
    neck = pelvis + TORSO * up
    head_c = neck + (HEAD_R + 0.04) * up
    shoulder = pelvis + 0.92 * TORSO * up

    joints: dict[str, Any] = {"pelvis": pelvis, "neck": neck, "head": head_c, "shoulder": shoulder}
    for side in ("f", "b"):
        joints[f"elbow_{side}"] = ray(shoulder, angles[f"shoulder_{side}"], UPPER_ARM)
        joints[f"wrist_{side}"] = ray(
            joints[f"elbow_{side}"], angles[f"shoulder_{side}"] + angles[f"elbow_{side}"], LOWER_ARM
        )
        joints[f"knee_{side}"] = ray(pelvis, angles[f"hip_{side}"], UPPER_LEG)
        joints[f"foot_{side}"] = ray(
            joints[f"knee_{side}"], angles[f"hip_{side}"] + angles[f"knee_{side}"], LOWER_LEG
        )

    lowest = min(min(float(pt[1]) for pt in joints.values()), float(head_c[1]) - HEAD_R)
    mirror = -1.0 if facing == "left" else 1.0
    base = np.array([float(at[0]), float(at[1]), 0.0])
    for name, pt in joints.items():
        joints[name] = base + scale * np.array([mirror * float(pt[0]), float(pt[1]) - lowest, 0.0])

    colour = PALETTE.highlight
    head = Circle(radius=HEAD_R * scale, color=colour, fill_opacity=1.0, stroke_width=3)
    head.move_to(joints["head"])
    torso = Line(joints["pelvis"], joints["neck"], color=colour, stroke_width=5)
    limbs = VGroup()
    for side in ("b", "f"):  # trailing limbs drawn first, so the leading side reads on top
        limbs.add(
            Line(joints["shoulder"], joints[f"elbow_{side}"], color=colour, stroke_width=3.6),
            Line(joints[f"elbow_{side}"], joints[f"wrist_{side}"], color=colour, stroke_width=3.6),
            Line(joints["pelvis"], joints[f"knee_{side}"], color=colour, stroke_width=4.2),
            Line(joints[f"knee_{side}"], joints[f"foot_{side}"], color=colour, stroke_width=4.2),
        )
    return VGroup(limbs, torso, head), joints


def _pendulum_sweep(anchor: Any, wrist: Any) -> tuple[float, float, float]:
    """Radius, start angle and mirror sweep of the wrist's pendulum circle.

    The sweep mirrors the wrist's angle about the vertical through the anchor
    and shrinks until the whole arc stays on stage.
    """
    import numpy as np

    v = wrist - anchor
    r = float(np.linalg.norm(v[:2]))
    phi = math.atan2(float(v[1]), float(v[0]))
    sweep = -math.pi - 2.0 * phi
    if abs(sweep) < 0.3:
        sweep = -0.9 if float(v[0]) >= 0 else 0.9
    for _ in range(40):
        thetas = [phi + sweep * i / 24 for i in range(25)]
        xs = [float(anchor[0]) + r * math.cos(t) for t in thetas]
        ys = [float(anchor[1]) + r * math.sin(t) for t in thetas]
        if max(abs(x) for x in xs) <= 4.55 and min(ys) >= 0.05:
            break
        sweep *= 0.88
    return r, phi, sweep


def _mirror_delta(centre: Any, start: Any) -> float:
    """Signed sweep taking `start` to its mirror across the vertical below `centre`.

    A pendulum released at an angle returns to the same height on the other
    side; this is that sweep, computed from live coordinates at play time and
    shrunk until the swept point stays on stage.
    """
    import numpy as np

    v = start - centre
    r = float(np.linalg.norm(v[:2]))
    phi = math.atan2(float(v[1]), float(v[0]))
    delta = -math.pi - 2.0 * phi
    if abs(delta) < 0.25:
        delta = -0.9 if float(v[0]) >= 0 else 0.9
    for _ in range(40):
        end = centre + r * np.array([math.cos(phi + delta), math.sin(phi + delta), 0.0])
        if abs(float(end[0])) <= 6.3 and float(end[1]) >= -3.7:
            break
        delta *= 0.85
    return delta


def _spun(point: Any, angle: float, about: Any) -> Any:
    """`point` rotated by `angle` radians around `about`, as a plain array."""
    import numpy as np

    c, s = math.cos(angle), math.sin(angle)
    v = point - about
    return about + np.array([c * float(v[0]) - s * float(v[1]), s * float(v[0]) + c * float(v[1]), 0.0])


def _catenary_points(p0: Any, p1: Any, *, min_y: float = 0.06, samples: int = 36) -> tuple[list[Any], float]:
    """Points of y = a cosh((x - xv)/a) + c through both endpoints, sag kept above min_y.

    The vertex comes from the identity cosh P - cosh Q = 2 sinh((P+Q)/2)
    sinh((P-Q)/2), which gives xv in closed form; a grows until the sag
    clears, so the curve is a genuine catenary at every parameter.
    """
    import numpy as np

    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    if x1 < x0:
        x0, y0, x1, y1 = x1, y1, x0, y0
    span = x1 - x0
    if span < 0.05:
        return [], 0.0
    a = 0.6 * span
    points: list[Any] = []
    for _ in range(8):
        xv = (x0 + x1) / 2 - a * math.asinh((y1 - y0) / (2 * a * math.sinh(span / (2 * a))))
        c = y0 - a * math.cosh((x0 - xv) / a)
        points = [
            np.array([x, a * math.cosh((x - xv) / a) + c, 0.0])
            for x in (x0 + span * i / (samples - 1) for i in range(samples))
        ]
        if min(float(pt[1]) for pt in points) >= min_y:
            break
        a *= 1.6
    return points, a


def _leap_track(x_start: float, direction: float, y0: float = 0.0) -> tuple[list[Any], float, float]:
    """A 45-degree projectile arc from x_start. The apex is span/4 — physics, not style."""
    import numpy as np

    x_end = min(max(x_start + 1.5 * direction, -4.45), 4.45)
    span = x_end - x_start
    if abs(span) < 0.35:
        return [], 0.0, 0.0
    apex = abs(span) / 4.0
    points = [
        np.array([x_start + span * i / 35, y0 + 4 * apex * (i / 35) * (1 - i / 35), 0.0])
        for i in range(36)
    ]
    return points, apex, span


def _dashed(points: list[Any], *, num_dashes: int = 24) -> Any:
    """One dashed accent guide through the given points — the only maths decoration allowed."""
    from manim import DashedVMobject, VMobject

    curve = VMobject(color=PALETTE.accent, stroke_width=1.8)
    curve.set_points_smoothly(points)
    guide = DashedVMobject(curve, num_dashes=num_dashes)
    guide.set_stroke(opacity=0.7)
    return guide


# ---------------------------------------------------------------------------
# ProofMotion's forms. Each builder returns (pieces, draw order, geometry,
# facts) so the component and math_scene share one construction.
# ---------------------------------------------------------------------------


def _orb_form(*, seed: int, jitter: float, at_x: float, radius: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """A jittered vertex ring, boundary polygon, random chords, dots, glow, particles."""
    import numpy as np
    from manim import Dot, Line, Polygon, VGroup

    rng = random.Random(seed)
    vertices, chords = 16, 24
    points = []
    for i in range(vertices):
        theta = 2 * math.pi * i / vertices + jitter * rng.uniform(-1.0, 1.0)
        rr = radius * (1.0 + jitter * rng.uniform(-0.9, 0.9))
        points.append(np.array([at_x + rr * math.cos(theta), rr * math.sin(theta), 0.0]))

    boundary = Polygon(*points, color=PALETTE.ink, stroke_width=2.4, fill_opacity=0.0)
    chosen: set[tuple[int, int]] = set()
    while len(chosen) < chords:
        i, k = rng.randrange(vertices), rng.randrange(vertices)
        if i != k:
            chosen.add((min(i, k), max(i, k)))
    chord_lines = VGroup(*[
        Line(points[i], points[k], color=PALETTE.ink, stroke_width=1.2, stroke_opacity=0.75)
        for i, k in sorted(chosen)
    ])
    dots = VGroup(*[Dot(pt, radius=0.045, color=PALETTE.accent) for pt in points])
    glow = _halo(boundary)
    particles = VGroup()
    for _ in range(6):
        angle = rng.uniform(0.0, 2 * math.pi)
        rr = radius * rng.uniform(1.16, 1.45)
        particles.add(Dot(
            np.array([at_x + rr * math.cos(angle), rr * math.sin(angle), 0.0]),
            radius=0.022, color=PALETTE.accent, fill_opacity=0.7,
        ))

    lengths = [float(np.linalg.norm(points[i] - points[k])) for i, k in chosen]
    pieces = {"glow": glow, "chords": chord_lines, "boundary": boundary, "dots": dots, "particles": particles}
    order = ["glow", "chords", "boundary", "dots", "particles"]
    geom = {"centre": np.array([at_x, 0.0, 0.0]), "radius": radius}
    facts = f"orb of {vertices} vertices and {len(chosen)} chords, mean chord {sum(lengths) / len(lengths):.2f}"
    return pieces, order, geom, facts


def _swing_line_form(*, seed: int, jitter: float, at_x: float, span: float, height: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """Two masts and a real catenary strung between their tops."""
    import numpy as np
    from manim import Dot, Line, VGroup, VMobject

    rng = random.Random(seed)
    top_l = np.array([at_x - span / 2, height, 0.0])
    top_r = np.array([at_x + span / 2, height, 0.0])
    masts = VGroup(
        Line([float(top_l[0]), 0, 0], top_l, color=PALETTE.ink, stroke_width=3),
        Line([float(top_r[0]), 0, 0], top_r, color=PALETTE.ink, stroke_width=3),
        Dot(top_l, radius=0.05, color=PALETTE.accent),
        Dot(top_r, radius=0.05, color=PALETTE.accent),
    )
    points, a = _catenary_points(top_l, top_r)
    if jitter:
        points = [points[0]] + [
            pt + np.array([0.0, jitter * rng.uniform(-1.0, 1.0), 0.0]) for pt in points[1:-1]
        ] + [points[-1]]
    curve = VMobject(color=PALETTE.ink, stroke_width=2.4)
    curve.set_points_smoothly(points)
    cable = _glowed(curve, colour=PALETTE.bad if jitter else None)
    sag = height - min(float(pt[1]) for pt in points)
    pieces = {"masts": masts, "cable": cable}
    geom = {"cable_points": points, "tops": (top_l, top_r), "a": a}
    facts = f"masts {height:g} tall; the cable is the catenary a = {a:.2f}, sag {sag:.2f}"
    return pieces, ["masts", "cable"], geom, facts


def _ramp_form(*, seed: int, jitter: float, at_x: float, span: float, height: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """A smooth incline — cubic easing from the ground to its height — on thin supports."""
    import numpy as np
    from manim import Line, VGroup, VMobject

    rng = random.Random(seed)
    x0, x1 = at_x - span / 2, at_x + span / 2

    def y_of(x: float) -> float:
        t = min(max((x - x0) / span, 0.0), 1.0)
        return height * (3 * t * t - 2 * t * t * t)

    points = [np.array([x0 + span * i / 35, y_of(x0 + span * i / 35), 0.0]) for i in range(36)]
    if jitter:
        points = [points[0]] + [
            pt + np.array([0.0, jitter * rng.uniform(-1.0, 1.0), 0.0]) for pt in points[1:-1]
        ] + [points[-1]]
    curve = VMobject(color=PALETTE.ink, stroke_width=2.6)
    curve.set_points_smoothly(points)
    surface = _glowed(curve, colour=PALETTE.bad if jitter else None)
    supports = VGroup()
    x = x0 + 0.9
    while x < x1 - 0.15:
        if y_of(x) > 0.18:
            supports.add(Line([x, 0, 0], [x, y_of(x), 0], color=PALETTE.muted, stroke_width=1.4))
        x += 0.9
    pieces = {"supports": supports, "surface": surface}
    geom = {"track": points, "y_of": y_of, "x0": x0, "x1": x1, "top": height}
    facts = f"ramp climbs {height:g} over {span:g} on a cubic easing, {height / span * 100:.0f}% mean grade"
    return pieces, ["supports", "surface"], geom, facts


def _spiral_form(*, seed: int, jitter: float, at_x: float, span: float, height: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """Seven nested quarter-arcs whose radii grow by the golden ratio."""
    import numpy as np
    from manim import Dot, VGroup, VMobject

    rng = random.Random(seed)
    phi_ratio = (1 + math.sqrt(5)) / 2
    centre = np.zeros(3)
    theta, r = math.pi, 1.0
    raw: list[Any] = []
    joints_at: list[int] = []
    for _ in range(7):
        joints_at.append(len(raw))
        for i in range(13):
            t = theta + (math.pi / 2) * i / 12
            raw.append(centre + r * np.array([math.cos(t), math.sin(t), 0.0]))
        theta += math.pi / 2
        centre = centre + (r - r * phi_ratio) * np.array([math.cos(theta), math.sin(theta), 0.0])
        r *= phi_ratio

    xs = [float(pt[0]) for pt in raw]
    ys = [float(pt[1]) for pt in raw]
    scale = min(span / (max(xs) - min(xs)), height / (max(ys) - min(ys)))
    cx = (max(xs) + min(xs)) / 2
    points = [
        np.array([(float(pt[0]) - cx) * scale + at_x, (float(pt[1]) - min(ys)) * scale + 0.25, 0.0])
        for pt in raw
    ]
    if jitter:
        points = [
            pt + 0.6 * jitter * np.array([rng.uniform(-1.0, 1.0), rng.uniform(-1.0, 1.0), 0.0])
            for pt in points
        ]
    curve = VMobject(color=PALETTE.ink, stroke_width=2.4)
    curve.set_points_smoothly(points)
    spiral = _glowed(curve, colour=PALETTE.bad if jitter else None)
    joints = VGroup(*[Dot(points[i], radius=0.04, color=PALETTE.accent) for i in joints_at])
    pieces = {"spiral": spiral, "joints": joints}
    # Heart outward: a rider ends on the wide outer arc, clear of the tight coils.
    geom = {"track": list(points)}
    facts = f"7 quarter-arcs, radii in the golden ratio {phi_ratio:.3f}"
    return pieces, ["spiral", "joints"], geom, facts


def _arches_form(*, seed: int, jitter: float, at_x: float, span: float, height: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """A row of parabolic arches standing on the ground line."""
    import numpy as np
    from manim import VGroup, VMobject

    rng = random.Random(seed)
    count = max(2, min(4, round(span / 2.0)))
    width = span / count
    x0 = at_x - span / 2
    arches = VGroup()
    for k in range(count):
        apex = height * (1.0 + (jitter * rng.uniform(-0.5, 0.5) if jitter else 0.0))
        pts = [
            np.array([x0 + k * width + width * i / 23, 4 * apex * (i / 23) * (1 - i / 23), 0.0])
            for i in range(24)
        ]
        curve = VMobject(color=PALETTE.ink, stroke_width=2.4)
        curve.set_points_smoothly(pts)
        arches.add(curve)
    glow = _halo(arches, colour=PALETTE.bad if jitter else None)
    pieces = {"glow": glow, "arches": arches}
    geom = {"count": count, "width": width}
    facts = f"{count} parabolic arches, {width:.2f} wide, apex {height:g}"
    return pieces, ["glow", "arches"], geom, facts


def _steps_form(*, seed: int, jitter: float, at_x: float, span: float, height: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """A staircase quantising a slope into risers and treads."""
    import numpy as np
    from manim import VGroup, VMobject

    rng = random.Random(seed)
    count = 5
    run = span / count
    x0 = at_x - span / 2
    rises = [1.0 + (0.12 * rng.uniform(-1.0, 1.0) if jitter else 0.0) for _ in range(count)]
    factor = height / sum(rises)
    rises = [rise * factor for rise in rises]

    steps = VGroup()
    treads: list[tuple[float, float, float]] = []
    y = 0.0
    for k in range(count):
        x = x0 + k * run
        y1 = y + rises[k]
        step = VMobject(color=PALETTE.ink, stroke_width=2.4)
        step.set_points_as_corners([
            np.array([x, y, 0.0]), np.array([x, y1, 0.0]), np.array([x + run, y1, 0.0]),
        ])
        steps.add(step)
        treads.append((x, x + run, y1))
        y = y1
    glow = _halo(steps, colour=PALETTE.bad if jitter else None)
    pieces = {"glow": glow, "steps": steps}
    geom = {"treads": treads, "top": y, "x0": x0}
    facts = f"{count} steps quantise a {height:g} rise over {span:g}, mean rise {height / count:.2f}"
    return pieces, ["glow", "steps"], geom, facts


#: Per-form sizing chosen when the caller passes 0 ("choose for me").
FORM_DEFAULTS: dict[str, tuple[float, float]] = {
    "orb": (0.0, 2.8),        # span unused; height is the orb's diameter
    "swing_line": (5.6, 3.4),
    "ramp": (5.0, 2.2),
    "spiral": (4.2, 3.2),
    "arches": (6.0, 1.6),
    "steps": (5.0, 2.4),
}


def _world_form(form: str, *, seed: int, mood: str, at_x: float, span: float, height: float) -> tuple[dict[str, Any], list[str], dict[str, Any], str]:
    """Build one of ProofMotion's forms; agitated moods jitter it and tint the glow."""
    default_span, default_height = FORM_DEFAULTS[form]
    span = span or default_span
    height = height or default_height
    agitated = mood == "agitated"
    if form == "orb":
        pieces, order, geom, facts = _orb_form(
            seed=seed, jitter=0.20 if agitated else 0.09, at_x=at_x, radius=height / 2,
        )
        if agitated:
            pieces["glow"].set_stroke(color=PALETTE.bad)
        return pieces, order, geom, facts
    builder = {
        "swing_line": _swing_line_form, "ramp": _ramp_form, "spiral": _spiral_form,
        "arches": _arches_form, "steps": _steps_form,
    }[form]
    return builder(seed=seed, jitter=0.05 if agitated else 0.0, at_x=at_x, span=span, height=height)


class SpyderMathParams(BaseModel):
    """A minimal glowing stick-figure human with a few mathematical tools."""

    pose: str = Field(
        default="stand",
        description="Named pose, e.g. 'swing', 'run_contact' or 'dab'. One of: " + ", ".join(sorted(POSES)) + ".",
    )
    facing: Literal["left", "right"] = Field(
        default="right", description="Which way the hero faces, e.g. 'right'.",
    )
    at_x: float = Field(
        default=0.0, ge=-4, le=4,
        description="Horizontal position on the stage, e.g. -2.5. 0 is centre stage.",
    )
    web: bool = Field(
        default=False,
        description="Draw a web line from the leading wrist up to an anchor, e.g. true for a swing entrance.",
    )
    anchor_x: float = Field(
        default=2.0, ge=-4, le=4, description="Web anchor x, e.g. 2.0. Used when web is true.",
    )
    anchor_y: float = Field(
        default=3.2, ge=1, le=4, description="Web anchor height, e.g. 3.2. Used when web is true.",
    )
    show_maths: bool = Field(
        default=False,
        description="Draw one dashed guide for the governing curve — pendulum arc, catenary, or leap parabola.",
    )
    region: str = "stage"

    @field_validator("pose")
    @classmethod
    def _a_known_pose(cls, pose: str) -> str:
        if pose not in POSES:
            raise ValueError(
                f"unknown pose {pose!r}; choose one of: {', '.join(sorted(POSES))}."
            )
        return pose


@component(version=2, domain="story", params=SpyderMathParams)
def spyder_math(p: SpyderMathParams) -> Built:
    """A stick-figure hero character in action — Spyder Math runs, swings a web, leaps, pulls funny poses.

    An original glowing stick figure, not a picture of anyone, and deliberately
    minimal: the figure, the ground, optionally a web. His tools are
    mathematics the component computes — the web is a taut line from wrist to
    anchor, a swing is an arc of the circle of radius |wrist - anchor|, a leap
    is the 45-degree projectile parabola whose apex is a quarter of its range.
    """
    import numpy as np
    from manim import Dot, Line, VGroup

    scale = 1.15
    raw, joints = _stick_figure(p.pose, at=(p.at_x, 0.0), scale=scale, facing=p.facing)
    figure = _glowed(raw)
    ground = Line([-4.6, 0, 0], [4.6, 0, 0], color=PALETTE.muted, stroke_width=2)

    parts: dict[str, Any] = {"ground": ground, "figure": figure}
    group = VGroup(ground, figure)
    beats: list[list[str]] = [["ground"], ["figure"]]
    notes = [f"pose {p.pose}, facing {p.facing}, figure {float(raw.height):.2f} units tall"]

    anchor_pt = np.array([p.anchor_x, p.anchor_y, 0.0])
    wrist = joints["wrist_f"]
    anchor_dot = web = None
    reveal: list[str] = []

    if p.web:
        anchor_dot = Dot(anchor_pt, radius=0.055, color=PALETTE.accent)
        strand = Line(anchor_pt, wrist, color=PALETTE.accent, stroke_width=2.5)
        web = _glowed(strand)
        parts["web"], parts["anchor"] = web, anchor_dot
        group.add(web, anchor_dot)
        reveal += ["web", "anchor"]
        length = float(np.linalg.norm(wrist - anchor_pt))
        notes.append(f"web length {length:.2f} from wrist to anchor ({p.anchor_x:g}, {p.anchor_y:g})")

    if p.show_maths:
        # At most one dashed guide, and never a label: the hero stays minimal.
        maths = None
        if p.web and p.pose == "swing":
            r, phi, sweep = _pendulum_sweep(anchor_pt, wrist)
            arc = [
                anchor_pt + r * np.array([math.cos(phi + sweep * i / 24), math.sin(phi + sweep * i / 24), 0.0])
                for i in range(25)
            ]
            maths = _dashed(arc)
            notes.append(f"swing sweeps {abs(math.degrees(sweep)):.0f} degrees on radius {r:.2f}")
        elif p.web:
            points, a = _catenary_points(wrist, anchor_pt)
            if points:
                maths = _dashed(points)
                notes.append(f"slack web is the catenary a = {a:.2f}")
        elif p.pose.startswith("run_"):
            direction = 1.0 if p.facing == "right" else -1.0
            points, apex, span = _leap_track(p.at_x + 0.5 * direction, direction)
            if points:
                maths = _dashed(points, num_dashes=18)
                notes.append(f"leap parabola spans {abs(span):.2f}, apex {apex:.2f} = span/4")
        if maths is not None:
            parts["maths"] = maths
            group.add(maths)
            reveal.append("maths")

    if reveal:
        beats.append(reveal)

    place(group, layout("title_stage_caption")[p.region])

    if p.pose == "swing" and p.web:
        def act() -> Any:
            """Figure and web swing rigidly about the anchor, so the rope never detaches."""
            from manim import Rotate, VGroup

            anchor_now = anchor_dot.get_center()
            delta = _mirror_delta(anchor_now, strand.get_end())
            return Rotate(VGroup(figure, web), angle=delta, about_point=anchor_now, run_time=2.4)
    elif p.pose.startswith("run_"):
        def act() -> Any:
            """A short dash of two projectile hops, so the run bobs instead of gliding."""
            from manim import MoveAlongPath, VMobject

            direction = 1.0 if p.facing == "right" else -1.0
            start = figure.get_center()
            x0, y0 = float(start[0]), float(start[1])
            target = min(max(x0 + 1.3 * direction, -4.2), 4.2)
            span = target - x0
            if abs(span) < 0.2:
                span = -0.6 * direction
            hop_h = abs(span) / 8.0  # each of two hops is a 45-degree parabola: apex = hop span / 4
            points = []
            for hop in range(2):
                for i in range(13):
                    t = i / 12
                    points.append(np.array([x0 + span * (hop + t) / 2, y0 + 4 * hop_h * t * (1 - t), 0.0]))
            path = VMobject()
            path.set_points_smoothly(points)
            return MoveAlongPath(figure, path, run_time=1.5)
    elif p.pose in ("dab", "flail"):
        def act() -> Any:
            """A comic little wiggle — the funny poses are meant to be laughed at."""
            from manim import Wiggle

            return Wiggle(figure, scale_value=1.06, rotation_angle=0.035, run_time=1.2)
    else:
        def act() -> Any:
            """A subtle breathing pulse, so a held pose still reads as alive."""
            from manim import ScaleInPlace, there_and_back

            return ScaleInPlace(figure, 1.05, rate_func=there_and_back, run_time=1.6)

    return Built(group=group, parts=parts, beats=beats, motions=[act], notes="; ".join(notes))


class ProofMotionParams(BaseModel):
    """Geometry that takes any form and builds an environment."""

    form: Literal["orb", "swing_line", "ramp", "spiral", "arches", "steps"] = Field(
        default="orb", description="Which form the geometry takes, e.g. 'swing_line' or 'ramp'.",
    )
    seed: int = Field(default=7, description="Seed for the deterministic construction, e.g. 7.")
    mood: Literal["calm", "agitated"] = Field(
        default="calm", description="calm is steady; agitated jitters the form and tints its glow.",
    )
    at_x: float = Field(
        default=0.0, ge=-4, le=4, description="Horizontal position on the stage, e.g. 1.5. 0 is centre stage.",
    )
    span: float = Field(
        default=0.0, ge=0, le=9,
        description="Overall width in scene units, e.g. 6.0. 0 chooses a sensible width per form.",
    )
    height: float = Field(
        default=0.0, ge=0, le=4.2,
        description="Overall height in scene units, e.g. 2.5. 0 chooses a sensible height per form.",
    )
    region: str = "stage"

    @field_validator("span")
    @classmethod
    def _usable_span(cls, span: float) -> float:
        if 0 < span < 1.5:
            raise ValueError(f"span {span:g} is too narrow to draw; give at least 1.5, or 0 to choose per form.")
        return span

    @field_validator("height")
    @classmethod
    def _usable_height(cls, height: float) -> float:
        if 0 < height < 0.8:
            raise ValueError(f"height {height:g} is too low to draw; give at least 0.8, or 0 to choose per form.")
        return height


@component(version=1, domain="story", params=ProofMotionParams)
def proofmotion(p: ProofMotionParams) -> Built:
    """Geometry that takes any form — ProofMotion builds the world and environment the hero acts in: anchors, ramps, spirals, arches, steps.

    Not a creature: a shape-shifter. Every form is real construction — the
    swing line is a genuine catenary, the ramp a cubic easing, the spiral
    golden-ratio quarter-arcs, the steps a quantised slope — and every form is
    deterministic under its seed.
    """
    from manim import VGroup

    pieces, order, _, facts = _world_form(
        p.form, seed=p.seed, mood=p.mood, at_x=p.at_x, span=p.span, height=p.height,
    )
    group = VGroup(*[pieces[name] for name in order])
    parts: dict[str, Any] = dict(pieces)
    place(group, layout("title_stage_caption")[p.region])

    beats_of = {
        "orb": [["boundary", "glow"], ["chords"], ["dots", "particles"]],
        "swing_line": [["masts"], ["cable"]],
        "ramp": [["supports"], ["surface"]],
        "spiral": [["spiral"], ["joints"]],
        "arches": [["glow", "arches"]],
        "steps": [["glow", "steps"]],
    }

    motions: list[Any] = []
    if p.form == "orb":
        def turn() -> Any:
            """The orb revolves about its own centre — slower when calm."""
            from manim import Rotate

            return Rotate(group, angle=math.tau / (8 if p.mood == "calm" else 4), run_time=3.0)

        motions.append(turn)
        if p.mood == "agitated":
            def shudder() -> Any:
                """Seeded jolts, each there-and-back, while the glow swells once."""
                import numpy as np
                from manim import AnimationGroup, ApplyMethod, ScaleInPlace, Succession, there_and_back

                rng = random.Random(p.seed + 101)
                jolts = [
                    ApplyMethod(
                        group.shift,
                        np.array([rng.uniform(-0.08, 0.08), rng.uniform(-0.08, 0.08), 0.0]),
                        rate_func=there_and_back, run_time=0.14,
                    )
                    for _ in range(6)
                ]
                return AnimationGroup(
                    Succession(*jolts),
                    ScaleInPlace(pieces["glow"], 1.2, rate_func=there_and_back, run_time=0.84),
                )

            motions.append(shudder)
    elif p.form == "swing_line":
        def sway() -> Any:
            """The cable sways gently, there and back."""
            import numpy as np
            from manim import ApplyMethod, there_and_back

            return ApplyMethod(
                pieces["cable"].shift, np.array([0.08, 0.0, 0.0]),
                rate_func=there_and_back, run_time=1.8,
            )

        motions.append(sway)
    elif p.form == "ramp":
        def shimmer() -> Any:
            """The support chords catch the light one after another."""
            from manim import Indicate, ScaleInPlace, Succession, there_and_back

            supports = list(pieces["supports"])
            if not supports:
                return ScaleInPlace(pieces["surface"], 1.02, rate_func=there_and_back, run_time=1.2)
            return Succession(*[
                Indicate(chord, scale_factor=1.06, color=PALETTE.accent) for chord in supports
            ])

        motions.append(shimmer)
    elif p.form == "spiral":
        def revolve() -> Any:
            """The spiral turns slowly about its own centre."""
            from manim import Rotate

            return Rotate(group, angle=math.tau / 10, run_time=3.0)

        motions.append(revolve)
    elif p.form == "arches":
        def pulse() -> Any:
            """A pulse travels the row, arch to arch."""
            from manim import Indicate, Succession

            return Succession(*[Indicate(arch, color=PALETTE.accent) for arch in pieces["arches"]])

        motions.append(pulse)
    else:  # steps
        def rise() -> Any:
            """Each step lifts slightly in turn, bottom-up, as if settling into place."""
            import numpy as np
            from manim import ApplyMethod, Succession, there_and_back

            return Succession(*[
                ApplyMethod(step.shift, np.array([0.0, 0.07, 0.0]), rate_func=there_and_back, run_time=0.22)
                for step in pieces["steps"]
            ])

        motions.append(rise)

    return Built(
        group=group, parts=parts, beats=beats_of[p.form], motions=motions,
        notes=f"{facts}; mood {p.mood}",
    )


class MathSceneParams(BaseModel):
    """The hero inside a world ProofMotion built, one beat at a time."""

    beat: Literal["swing_across", "run_the_ramp", "climb_the_steps", "ride_the_spiral", "standoff"] = Field(
        default="swing_across", description="Which beat to stage, e.g. 'run_the_ramp'.",
    )
    seed: int = Field(default=7, description="Seed for the world's deterministic construction, e.g. 7.")
    hero_x: float = Field(
        default=0.0, ge=-4, le=4,
        description=(
            "Hero start position, e.g. -3.0. 0 chooses the natural start of the world. "
            "Ignored by swing_across, where the cable's grab point dictates where the hero hangs."
        ),
    )
    show_maths: bool = Field(
        default=False,
        description="Draw the computed trajectory the traversal follows, as one thin guide. No labels.",
    )
    region: str = "stage"


@component(version=2, domain="story", params=MathSceneParams)
def math_scene(p: MathSceneParams) -> Built:
    """Spyder Math moves through a world ProofMotion built — the hero swings, runs the ramp, climbs steps in a staged action scene.

    Each beat asks ProofMotion for the matching environment and computes the
    hero's traversal on it: pendulum arcs chained between the swing line's
    anchors, run poses with feet on the ramp's cubic curve, parabolic hops
    landing on the stair treads, a sweep along the golden spiral, or a quiet
    standoff with the orb. Every path is baked geometry, never an updater.
    """
    import numpy as np
    from manim import Dot, Line, VGroup, VMobject

    ground = Line([-4.6, 0, 0], [4.6, 0, 0], color=PALETTE.muted, stroke_width=2)
    parts: dict[str, Any] = {}
    notes: list[str] = [f"beat {p.beat}"]
    track_points: list[Any] = []
    web = None
    a1_dot = a2_dot = None

    if p.beat == "swing_across":
        pieces, order, geom, facts = _world_form(
            "swing_line", seed=p.seed, mood="calm", at_x=0.0, span=5.6, height=3.6,
        )
        cable = geom["cable_points"]
        # Grab points a quarter of the way in from each mast, where the cable is high.
        a1, a2 = cable[9], cable[26]
        a1_dot = Dot(a1, radius=0.05, color=PALETTE.accent)
        a2_dot = Dot(a2, radius=0.05, color=PALETTE.accent)
        world = VGroup(ground, *[pieces[name] for name in order], a1_dot, a2_dot)
        # hero_x is ignored here: the hero HANGS from the cable, placed below the
        # grab point after the rig is built. Ground placement means nothing mid-air.
        hero_pose, hero_at = "swing", (0.0, 0.0)
    elif p.beat == "run_the_ramp":
        pieces, order, geom, facts = _world_form(
            "ramp", seed=p.seed, mood="calm", at_x=0.4, span=5.6, height=2.2,
        )
        world = VGroup(ground, *[pieces[name] for name in order])
        x0, x1, y_of = geom["x0"], geom["x1"], geom["y_of"]
        hx = p.hero_x or x0 + 0.2
        hx = min(max(hx, x0 + 0.1), x1 - 1.0)
        hero_pose, hero_at = "run_contact", (hx, y_of(hx))
        track_points = [
            np.array([x, y_of(x), 0.0])
            for x in (hx + (x1 - 0.3 - hx) * i / 29 for i in range(30))
        ]
        notes.append(f"feet on the curve from y = {y_of(hx):.2f} up to {y_of(x1 - 0.3):.2f}")
    elif p.beat == "climb_the_steps":
        pieces, order, geom, facts = _world_form(
            "steps", seed=p.seed, mood="calm", at_x=1.2, span=4.6, height=2.3,
        )
        world = VGroup(ground, *[pieces[name] for name in order])
        x0 = geom["x0"]
        hx = p.hero_x or x0 - 1.0
        hx = min(max(hx, -4.2), x0 - 0.6)
        hero_pose, hero_at = "crouch", (hx, 0.0)
        landings = [np.array([hx, 0.0, 0.0])] + [
            np.array([(left + right) / 2, top, 0.0]) for left, right, top in geom["treads"]
        ]
        for start, end in zip(landings, landings[1:]):
            hop = max(0.18, float(end[0] - start[0]) / 4)  # never flatter than a quarter of the gap
            for i in range(12):
                t = i / 11
                track_points.append(start + t * (end - start) + np.array([0.0, 4 * hop * t * (1 - t), 0.0]))
        notes.append(f"{len(geom['treads'])} parabolic hops land on the treads, top at {geom['top']:.2f}")
    elif p.beat == "ride_the_spiral":
        pieces, order, geom, facts = _world_form(
            "spiral", seed=p.seed, mood="calm", at_x=0.8, span=4.2, height=3.2,
        )
        world = VGroup(ground, *[pieces[name] for name in order])
        track_points = geom["track"]
        start = track_points[0]
        hero_pose, hero_at = "flail", (float(start[0]), float(start[1]))
        notes.append("the hero rides the spiral from its heart out to the widest arc")
    else:  # standoff
        pieces, order, geom, facts = _world_form(
            "orb", seed=p.seed, mood="calm", at_x=2.4, span=0.0, height=2.1,
        )
        orb = VGroup(*[pieces[name] for name in order])
        orb.shift(np.array([0.0, 0.03 - float(orb.get_bottom()[1]), 0.0]))
        world = VGroup(ground, orb)
        hx = p.hero_x or -2.6
        hx = min(max(hx, -4.2), 0.3)
        hero_pose, hero_at = "stand", (hx, 0.0)
        notes.append(f"the hero regards the orb from {abs(2.4 - hx):.2f} units away")
    notes.append(facts)

    raw, joints = _stick_figure(hero_pose, at=hero_at, scale=1.05, facing="right")

    hang_theta = math.radians(38.0)
    rope_len = 0.55
    if p.beat == "swing_across":
        # The hero hangs mid-air: wrists at the rope's end, body along the rope,
        # swung back ready to sweep forward. Feet never touch the ground here.
        grab = a1 + rope_len * np.array([-math.sin(hang_theta), -math.cos(hang_theta), 0.0])
        shift = grab - joints["wrist_f"]
        raw.shift(shift)
        for name in list(joints):
            joints[name] = joints[name] + shift
        # Tilt the whole body to hang along the rope. The wrist is the pivot,
        # so joints["wrist_f"] stays exact; the other joints are not used after this.
        raw.rotate(-hang_theta, about_point=grab)
        notes.append(
            f"hero hangs {float(raw.get_bottom()[1]):.2f} above the ground on a {rope_len:g} rope"
        )

    hero = _glowed(raw)
    group = VGroup(world, hero)
    parts["world"], parts["hero"] = world, hero
    beats: list[list[str]] = [["world"], ["hero"]]

    catch_line = None
    if p.beat == "swing_across":
        strand = Line(a1_dot.get_center(), joints["wrist_f"], color=PALETTE.accent, stroke_width=2.5)
        web = _glowed(strand)
        parts["web"] = web
        group.add(web)
        # The web appears with the hero: a figure hanging in mid-air must never
        # be on screen without the rope that holds it there.
        beats[-1].append("web")
        # The second rope, pre-built where the catch will happen and invisible
        # until then — an animation that introduces a mobject mid-Succession
        # would flash it early, because play() adds the whole group up front.
        catch_theta = math.radians(35.0)
        hands_catch = a2 + rope_len * np.array([-math.sin(catch_theta), -math.cos(catch_theta), 0.0])
        catch_line = Line(a2, hands_catch, color=PALETTE.accent, stroke_width=2.5, stroke_opacity=0.0)
        group.add(catch_line)
        r, phi, sweep = _pendulum_sweep(a1_dot.get_center(), joints["wrist_f"])
        track_points = [
            a1_dot.get_center()
            + r * np.array([math.cos(phi + sweep * i / 24), math.sin(phi + sweep * i / 24), 0.0])
            for i in range(25)
        ]
        notes.append(f"first swing sweeps {abs(math.degrees(sweep)):.0f} degrees on radius {r:.2f}")

    track = None
    if track_points:
        # Baked in the group so every layout transform carries it, but never a
        # part and never visible: the motion reads its placed coordinates.
        track = VMobject(stroke_opacity=0.0, stroke_width=1.0)
        track.set_points_smoothly(track_points)
        group.add(track)
        if p.show_maths:
            trajectory = track.copy()
            trajectory.set_stroke(color=PALETTE.accent, width=1.6, opacity=0.5)
            parts["trajectory"] = trajectory
            group.add(trajectory)
            beats.append(["trajectory"])

    place(group, layout("title_stage_caption")[p.region])

    if p.beat == "swing_across":
        def act() -> Any:
            """Swing rigidly about the first grab, release and fly, catch the second web, swing through.

            Rigid rotations keep the rope pinned at the cable and at the hands
            in every frame; the flight between anchors is a projectile arc.
            """
            from manim import AnimationGroup, MoveAlongPath, Rotate, Succession, VGroup, VMobject

            a1p, a2p = a1_dot.get_center(), a2_dot.get_center()
            hands0 = strand.get_end()
            d1 = _mirror_delta(a1p, hands0)
            hands1 = _spun(hands0, d1, a1p)
            c1 = _spun(hero.get_center(), d1, a1p)

            hands2 = catch_line.get_end()
            c2 = c1 + (hands2 - hands1)
            lift = max(0.3, 0.5 * float(np.linalg.norm(hands0 - a1p)))
            flight_points = [
                c1 + (c2 - c1) * t + np.array([0.0, 4 * lift * t * (1 - t), 0.0])
                for t in (i / 19 for i in range(20))
            ]
            flight = VMobject()
            flight.set_points_smoothly(flight_points)

            d3 = _mirror_delta(a2p, hands2)
            # The body left the first swing tilted; pivot about the hands so the
            # grip stays exactly at the new rope's end while the body rights itself.
            catch_theta = math.atan2(float((a2p - hands2)[0]), float((a2p - hands2)[1]))
            straighten = -catch_theta - (-hang_theta + d1)
            return Succession(
                Rotate(VGroup(hero, web), angle=d1, about_point=a1p, run_time=1.3),
                # The released web goes to stroke opacity 0 rather than FadeOut:
                # a removed mobject reappears when a later fade re-adds its group.
                AnimationGroup(MoveAlongPath(hero, flight), web.animate.set_stroke(opacity=0.0), run_time=0.8),
                AnimationGroup(
                    catch_line.animate.set_stroke(opacity=1.0),
                    Rotate(hero, angle=straighten, about_point=hands2),
                    run_time=0.25,
                ),
                Rotate(VGroup(hero, catch_line), angle=d3, about_point=a2p, run_time=1.2),
            )
    elif p.beat == "standoff":
        def act() -> Any:
            """The hero breathes; the orb turns slowly. Nobody moves first."""
            from manim import AnimationGroup, Rotate, ScaleInPlace, there_and_back

            return AnimationGroup(
                ScaleInPlace(hero, 1.04, rate_func=there_and_back),
                Rotate(world[1], angle=math.tau / 8),
                run_time=2.0,
            )
    else:
        def act() -> Any:
            """Carry the hero along the baked track, feet where the surface is."""
            from manim import MoveAlongPath

            path = track.copy()
            path.shift(hero.get_center() - track.get_start())
            return MoveAlongPath(hero, path, run_time=2.6)

    return Built(group=group, parts=parts, beats=beats, motions=[act], notes="; ".join(notes))
