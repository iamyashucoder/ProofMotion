"""Directable characters — a stick-figure hero, a living geometry, and their duel.

The library drew apparatus: axes, springs, circuits. A question that is a story
— someone doing something, something reacting — had nowhere to go, and the
model hand-built figures out of raw Lines, differently and badly, every time.

These three are characters. Spyder Math is an original glowing stick figure
whose every ability is mathematics the component computes: a web is a taut line
or a catenary, a swing is a pendulum arc, a leap is a projectile parabola.
ProofMotion is a wireframe polyhedron orb — vertices, chords, glow — that
idles or hunts. math_duel stages them against each other, and every move in it
is a curve computed here, never a number taken on trust.
"""

from __future__ import annotations

import math
import random
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

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
}


def _glowed(mobject: Any, *, factor: float = 3.0, opacity: float = 0.13) -> Any:
    """A soft halo behind a stroke: the same geometry, wider and fainter."""
    from manim import VGroup

    halo = mobject.copy()
    for piece in halo.family_members_with_points():
        piece.set_fill(opacity=0.0)
        piece.set_stroke(width=float(piece.get_stroke_width()) * factor, opacity=opacity)
    return VGroup(halo, mobject)


def _stick_figure(
    pose: str, at: tuple[float, float] = (0.0, 0.0), scale: float = 1.0, facing: str = "right"
) -> tuple[Any, dict[str, Any]]:
    """The rig: head, torso, and two-segment limbs driven by a pose's joint angles.

    The lowest point of the pose is computed and set on y = 0 of the rig's
    local frame, so a grounded figure stands exactly on a ground line drawn at
    the same height. Returns (group, joints) — joints are final scene points,
    so a web can anchor to "wrist_f" without re-deriving the arm.
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


def _pendulum_guide(anchor: Any, wrist: Any) -> tuple[Any, float, float]:
    """Dashed arc of the wrist's pendulum circle, shrunk until it stays on stage.

    The radius is |wrist - anchor| and the sweep mirrors the wrist's angle
    about the vertical through the anchor — the actual swing, not a flourish.
    """
    import numpy as np
    from manim import Arc, DashedVMobject

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
    arc = Arc(radius=r, start_angle=phi, angle=sweep, arc_center=anchor,
              color=PALETTE.accent, stroke_width=1.8)
    guide = DashedVMobject(arc, num_dashes=24)
    guide.set_stroke(opacity=0.75)
    return guide, r, sweep


def _catenary_guide(p0: Any, p1: Any) -> tuple[Any, float]:
    """Dashed y = a cosh((x - xv)/a) + c through both points, sag kept off the ground.

    The vertex comes from the identity cosh P - cosh Q = 2 sinh((P+Q)/2)
    sinh((P-Q)/2), which gives xv in closed form; a grows until the sag clears
    the ground line, so the curve is a genuine catenary at every parameter.
    """
    import numpy as np
    from manim import DashedVMobject, VMobject

    x0, y0 = float(p0[0]), float(p0[1])
    x1, y1 = float(p1[0]), float(p1[1])
    if x1 < x0:
        x0, y0, x1, y1 = x1, y1, x0, y0
    span = x1 - x0
    if span < 0.05:
        return None, 0.0
    a = 0.75 * span
    points: list[Any] = []
    for _ in range(8):
        xv = (x0 + x1) / 2 - a * math.asinh((y1 - y0) / (2 * a * math.sinh(span / (2 * a))))
        c = y0 - a * math.cosh((x0 - xv) / a)
        points = [
            np.array([x, a * math.cosh((x - xv) / a) + c, 0.0])
            for x in (x0 + span * i / 35 for i in range(36))
        ]
        if min(float(pt[1]) for pt in points) >= 0.06:
            break
        a *= 1.6
    curve = VMobject(color=PALETTE.accent, stroke_width=1.8)
    curve.set_points_smoothly(points)
    guide = DashedVMobject(curve, num_dashes=26)
    guide.set_stroke(opacity=0.75)
    return guide, a


def _leap_guide(x_start: float, direction: float, y0: float = 0.0) -> tuple[Any, float, float, float]:
    """Dashed 45-degree projectile arc. The apex is span/4 — the physics, not a style."""
    import numpy as np
    from manim import DashedVMobject, VMobject

    x_end = min(max(x_start + 1.5 * direction, -4.45), 4.45)
    span = x_end - x_start
    if abs(span) < 0.35:
        return None, 0.0, 0.0, 0.0
    apex = abs(span) / 4.0
    points = [
        np.array([x_start + span * i / 35, y0 + 4 * apex * (i / 35) * (1 - i / 35), 0.0])
        for i in range(36)
    ]
    curve = VMobject(color=PALETTE.accent, stroke_width=1.8)
    curve.set_points_smoothly(points)
    guide = DashedVMobject(curve, num_dashes=20)
    guide.set_stroke(opacity=0.75)
    return guide, apex, x_start + span / 2, span


def _orb(
    *, vertices: int, chords: int, seed: int, radius: float, jitter: float,
    centre: tuple[float, float],
) -> tuple[dict[str, Any], list[Any], dict[str, float]]:
    """The wireframe orb, shared by proofmotion_orb and math_duel.

    A jittered ring of vertices, its boundary polygon, random chords, accent
    dots, a layered glow, and stray particles — all from one seeded RNG, so the
    same seed rebuilds the same creature to the last chord.
    """
    import numpy as np
    from manim import Dot, Line, Polygon, VGroup

    rng = random.Random(seed)
    cx, cy = float(centre[0]), float(centre[1])
    points = []
    for i in range(vertices):
        theta = 2 * math.pi * i / vertices + jitter * rng.uniform(-1.0, 1.0)
        rr = radius * (1.0 + jitter * rng.uniform(-0.9, 0.9))
        points.append(np.array([cx + rr * math.cos(theta), cy + rr * math.sin(theta), 0.0]))

    boundary = Polygon(*points, color=PALETTE.ink, stroke_width=2.4, fill_opacity=0.0)
    wanted = min(chords, vertices * (vertices - 1) // 2)
    chosen: set[tuple[int, int]] = set()
    while len(chosen) < wanted:
        i, k = rng.randrange(vertices), rng.randrange(vertices)
        if i != k:
            chosen.add((min(i, k), max(i, k)))
    chord_lines = VGroup(*[
        Line(points[i], points[k], color=PALETTE.ink, stroke_width=1.2, stroke_opacity=0.75)
        for i, k in sorted(chosen)
    ])
    dots = VGroup(*[Dot(pt, radius=0.045, color=PALETTE.accent) for pt in points])
    glow = VGroup(
        boundary.copy().set_fill(opacity=0.0).set_stroke(width=7.5, opacity=0.13),
        boundary.copy().set_fill(opacity=0.0).set_stroke(width=15.0, opacity=0.06),
    )
    particles = VGroup()
    for _ in range(6):
        angle = rng.uniform(0.0, 2 * math.pi)
        rr = radius * rng.uniform(1.16, 1.45)
        particles.add(Dot(
            np.array([cx + rr * math.cos(angle), cy + rr * math.sin(angle), 0.0]),
            radius=0.022, color=PALETTE.accent, fill_opacity=0.7,
        ))

    lengths = [float(np.linalg.norm(points[i] - points[k])) for i, k in chosen]
    facts = {
        "count": float(len(chosen)),
        "mean": sum(lengths) / len(lengths) if lengths else 0.0,
    }
    pieces = {"boundary": boundary, "chords": chord_lines, "dots": dots,
              "glow": glow, "particles": particles}
    return pieces, points, facts


class SpyderMathParams(BaseModel):
    """An original glowing stick-figure hero whose abilities are mathematics."""

    pose: str = Field(
        default="stand",
        description="Named pose, e.g. 'swing' or 'run_contact'. One of: " + ", ".join(sorted(POSES)) + ".",
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
        default=True,
        description="Dashed guide plus one short formula for the governing curve, e.g. the pendulum circle of a swing.",
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


@component(version=1, domain="story", params=SpyderMathParams)
def spyder_math(p: SpyderMathParams) -> Built:
    """A stick-figure hero character in action — spider-style web line, pendulum swing, projectile leap.

    An original glowing stick figure, not a picture of anyone. Every ability is
    mathematics the component computes: the web is a taut line from wrist to
    anchor (a catenary when slack), the swing is an arc of the circle of radius
    |wrist - anchor|, and a running leap follows the 45-degree projectile
    parabola whose apex is a quarter of its range.
    """
    import numpy as np
    from manim import Dot, Line, MathTex, VGroup

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
        maths = None
        if p.web and p.pose == "swing":
            guide, r, sweep = _pendulum_guide(anchor_pt, wrist)
            label = MathTex(f"r = {r:.2f}", font_size=22, color=PALETTE.accent)
            label.next_to(anchor_dot, np.array([0, 1, 0]), buff=0.2)
            maths = VGroup(guide, label)
            notes.append(f"swing sweeps {abs(math.degrees(sweep)):.0f} degrees on radius {r:.2f}")
        elif p.web:
            guide, a = _catenary_guide(wrist, anchor_pt)
            label = MathTex(r"y = a\cosh(x/a)", font_size=22, color=PALETTE.accent)
            label.next_to(anchor_dot, np.array([0, 1, 0]), buff=0.2)
            maths = VGroup(label) if guide is None else VGroup(guide, label)
            if guide is not None:
                notes.append(f"slack web is the catenary a = {a:.2f}")
        elif p.pose.startswith("run_"):
            direction = 1.0 if p.facing == "right" else -1.0
            guide, apex, apex_x, span = _leap_guide(p.at_x + 0.5 * direction, direction)
            if guide is not None:
                label = MathTex(r"h = \tfrac{R}{4}", font_size=22, color=PALETTE.accent)
                label.move_to(np.array([apex_x, apex + 0.55, 0.0]))
                maths = VGroup(guide, label)
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
            """Swing the whole figure along the pendulum arc, web pivoting at the anchor."""
            from manim import AnimationGroup, Arc, MoveAlongPath, Rotate

            a = anchor_dot.get_center()
            c = figure.get_center()
            v = c - a
            r_c = float(np.linalg.norm(v[:2]))
            phi = math.atan2(float(v[1]), float(v[0]))
            delta = -math.pi - 2.0 * phi
            if abs(delta) < 0.25:
                delta = -0.9 if float(v[0]) >= 0 else 0.9
            for _ in range(40):
                end = a + r_c * np.array([math.cos(phi + delta), math.sin(phi + delta), 0.0])
                if abs(float(end[0])) <= 6.3 and float(end[1]) >= -3.7:
                    break
                delta *= 0.85
            path = Arc(radius=r_c, start_angle=phi, angle=delta, arc_center=a)
            return AnimationGroup(
                MoveAlongPath(figure, path),
                Rotate(web, angle=delta, about_point=a),
                run_time=2.4,
            )
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
                    x = x0 + span * (hop + t) / 2
                    points.append(np.array([x, y0 + 4 * hop_h * t * (1 - t), 0.0]))
            path = VMobject()
            path.set_points_smoothly(points)
            return MoveAlongPath(figure, path, run_time=1.5)
    else:
        def act() -> Any:
            """A subtle breathing pulse, so a held pose still reads as alive."""
            from manim import ScaleInPlace, there_and_back

            return ScaleInPlace(figure, 1.05, rate_func=there_and_back, run_time=1.6)

    return Built(group=group, parts=parts, beats=beats, motions=[act], notes="; ".join(notes))


class ProofMotionOrbParams(BaseModel):
    """A living wireframe polyhedron orb, calm or agitated."""

    vertices: int = Field(default=16, ge=8, le=24, description="Vertices on the boundary ring, e.g. 16.")
    chords: int = Field(
        default=24, ge=10, le=40,
        description="Interior chords between random vertex pairs, e.g. 24. Capped at the distinct pairs available.",
    )
    seed: int = Field(default=7, description="Seed for the deterministic jitter and chord choice, e.g. 7.")
    mood: Literal["calm", "agitated"] = Field(
        default="calm", description="calm turns slowly; agitated jitters harder, vibrates, and pulses its glow.",
    )
    at_x: float = Field(
        default=0.0, ge=-4, le=4, description="Horizontal position on the stage, e.g. 1.5. 0 is centre stage.",
    )
    radius: float = Field(default=1.4, ge=0.8, le=2.2, description="Mean boundary radius in scene units, e.g. 1.4.")
    region: str = "stage"


@component(version=1, domain="story", params=ProofMotionOrbParams)
def proofmotion_orb(p: ProofMotionOrbParams) -> Built:
    """A living wireframe geometry creature — a chaotic polyhedron orb of vertices, chords and glow.

    Every vertex, chord and particle comes from one seeded RNG, so the same
    seed rebuilds the same creature and a different seed grows a different one.
    Calm, it turns slowly; agitated, it vibrates and its glow flares red.
    """
    from manim import VGroup

    jitter = 0.09 if p.mood == "calm" else 0.20
    pieces, _, facts = _orb(
        vertices=p.vertices, chords=p.chords, seed=p.seed,
        radius=p.radius, jitter=jitter, centre=(p.at_x, 0.0),
    )
    if p.mood == "agitated":
        for halo in pieces["glow"]:
            halo.set_stroke(color=PALETTE.bad)

    group = VGroup(pieces["glow"], pieces["chords"], pieces["boundary"], pieces["dots"], pieces["particles"])
    parts: dict[str, Any] = {name: pieces[name] for name in ("boundary", "chords", "dots", "glow", "particles")}
    place(group, layout("title_stage_caption")[p.region])

    def turn() -> Any:
        """The orb revolves about its own centre — slower when calm."""
        from manim import Rotate, VGroup as Core

        core = Core(pieces["glow"], pieces["chords"], pieces["boundary"], pieces["dots"])
        return Rotate(core, angle=math.tau / (8 if p.mood == "calm" else 4), run_time=3.0)

    motions = [turn]
    if p.mood == "agitated":
        def shudder() -> Any:
            """Seeded jolts, each there-and-back, while the glow swells once."""
            import numpy as np
            from manim import AnimationGroup, ApplyMethod, ScaleInPlace, Succession, there_and_back

            rng = random.Random(p.seed + 101)
            from manim import VGroup as Core

            core = Core(pieces["glow"], pieces["chords"], pieces["boundary"], pieces["dots"])
            jolts = [
                ApplyMethod(
                    core.shift,
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

    return Built(
        group=group, parts=parts,
        beats=[["boundary", "glow"], ["chords"], ["dots", "particles"]],
        motions=motions,
        notes=(
            f"{p.vertices} vertices, {facts['count']:.0f} chords, mean chord {facts['mean']:.2f} units; "
            f"radius {p.radius:g}, mood {p.mood}"
        ),
    )


class MathDuelParams(BaseModel):
    """Hero versus orb, one beat of the fight at a time."""

    beat: Literal["standoff", "chase", "swing_dodge", "web_capture"] = Field(
        default="standoff", description="Which beat of the duel to stage, e.g. 'swing_dodge'.",
    )
    hero_x: float = Field(
        default=-2.6, ge=-4, le=0, description="Hero position, left half of the stage, e.g. -2.6.",
    )
    orb_x: float = Field(
        default=2.6, ge=0, le=4, description="Orb position, right half of the stage, e.g. 2.6.",
    )
    seed: int = Field(default=7, description="Seed for the orb's deterministic jitter, e.g. 7.")
    show_maths: bool = Field(
        default=True,
        description="Dashed trajectory of the action plus one short label, e.g. the pendulum radius of a dodge.",
    )
    region: str = "stage"

    @model_validator(mode="after")
    def _air_between(self) -> MathDuelParams:
        gap = self.orb_x - self.hero_x
        if gap < 3.0:
            raise ValueError(
                f"hero at x={self.hero_x:g} and orb at x={self.orb_x:g} leave {gap:.2f} units "
                "between them; keep at least 3 so the fight has air."
            )
        return self


@component(version=1, domain="story", params=MathDuelParams)
def math_duel(p: MathDuelParams) -> Built:
    """A duel fight scene — stick-figure hero versus the geometry orb: chase, swing dodge, web capture.

    Every action is a computed curve: the standoff measures the gap, the chase
    hops on 45-degree parabolas while the orb advances, the dodge sweeps a
    pendulum arc about an anchor placed over the midpoint, and the capture
    winds a web polyline around the orb until its vibration decays.
    """
    import numpy as np
    from manim import DashedLine, Dot, Line, MathTex, VGroup, VMobject

    pose_of = {"standoff": "stand", "chase": "run_contact", "swing_dodge": "swing", "web_capture": "cast"}
    facing = "left" if p.beat == "chase" else "right"
    raw, joints = _stick_figure(pose_of[p.beat], at=(p.hero_x, 0.0), scale=1.05, facing=facing)
    hero = _glowed(raw)

    orb_radius = 1.05
    jitter = 0.18 if p.beat in ("chase", "swing_dodge") else 0.10
    pieces, orb_points, _ = _orb(
        vertices=14, chords=22, seed=p.seed, radius=orb_radius, jitter=jitter, centre=(p.orb_x, 0.0),
    )
    if p.beat == "chase":
        for halo in pieces["glow"]:
            halo.set_stroke(color=PALETTE.bad)
    orb = VGroup(pieces["glow"], pieces["chords"], pieces["boundary"], pieces["dots"], pieces["particles"])
    lift = 0.03 - float(orb.get_bottom()[1])
    orb.shift(np.array([0.0, lift, 0.0]))
    orb_centre = np.array([p.orb_x, lift, 0.0])
    wrap_radius = max(float(np.linalg.norm(pt - np.array([p.orb_x, 0.0, 0.0]))) for pt in orb_points) * 1.08

    ground = Line([-4.6, 0, 0], [4.6, 0, 0], color=PALETTE.muted, stroke_width=2)
    parts: dict[str, Any] = {"ground": ground, "hero": hero, "orb": orb}
    group = VGroup(ground, orb, hero)
    beats: list[list[str]] = [["ground"], ["hero", "orb"]]
    notes = [f"beat {p.beat}: hero at {p.hero_x:g}, orb at {p.orb_x:g}"]

    wrist = joints["wrist_f"]
    mid_x = (p.hero_x + p.orb_x) / 2
    anchor_dot = web = None
    trajectory = maths = None

    if p.beat == "swing_dodge":
        anchor_pt = np.array([mid_x, 3.45, 0.0])
        anchor_dot = Dot(anchor_pt, radius=0.055, color=PALETTE.accent)
        strand = Line(anchor_pt, wrist, color=PALETTE.accent, stroke_width=2.5)
        web = VGroup(_glowed(strand), anchor_dot)
        guide, r, sweep = _pendulum_guide(anchor_pt, wrist)
        notes.append(f"swing sweeps {abs(math.degrees(sweep)):.0f} degrees on radius {r:.2f}")
        if p.show_maths:
            trajectory = guide
            maths = MathTex(f"r = {r:.2f}", font_size=22, color=PALETTE.accent)
            maths.next_to(anchor_dot, np.array([0, 1, 0]), buff=0.2)
    elif p.beat == "web_capture":
        gamma0 = math.atan2(float(wrist[1] - orb_centre[1]), float(wrist[0] - orb_centre[0]))
        turns, segments = 1.25, 10
        wrap = [wrist]
        for k in range(segments + 1):
            angle = gamma0 - turns * math.tau * k / segments
            rr = wrap_radius * (1.0 - 0.18 * k / segments)
            wrap.append(orb_centre + rr * np.array([math.cos(angle), math.sin(angle), 0.0]))
        binding = VMobject(color=PALETTE.accent, stroke_width=2.2)
        binding.set_points_as_corners(wrap)
        web = _glowed(binding)
        length = sum(float(np.linalg.norm(b - a)) for a, b in zip(wrap, wrap[1:]))
        notes.append(f"web winds {turns:g} turns around the orb, length {length:.2f} units")
        if p.show_maths:
            trajectory = DashedLine(wrist, wrap[1], color=PALETTE.accent, stroke_width=1.8)
            trajectory.set_stroke(opacity=0.75)
            maths = MathTex(f"L = {length:.2f}", font_size=22, color=PALETTE.accent)
            maths.move_to(np.array([mid_x, 2.9, 0.0]))
    elif p.beat == "chase":
        guide, apex, _, span = _leap_guide(p.hero_x - 0.5, -1.0)
        if guide is not None:
            notes.append(f"flight hops span {abs(span):.2f}, apex {apex:.2f} = span/4")
        if p.show_maths and guide is not None:
            trajectory = guide
            maths = MathTex(r"h = \tfrac{R}{4}", font_size=22, color=PALETTE.accent)
            maths.move_to(np.array([mid_x, 2.9, 0.0]))
    else:  # standoff
        chest = joints["neck"]
        gap = float(np.linalg.norm(orb_centre - chest))
        notes.append(f"{gap:.2f} units apart, eye to centre")
        if p.show_maths:
            trajectory = DashedLine(chest, orb_centre, color=PALETTE.accent, stroke_width=1.8)
            trajectory.set_stroke(opacity=0.75)
            maths = MathTex(f"d = {gap:.2f}", font_size=22, color=PALETTE.accent)
            maths.move_to(np.array([mid_x, 2.9, 0.0]))

    if web is not None:
        parts["web"] = web
        group.add(web)
        beats.append(["web"])
    reveal = []
    if trajectory is not None:
        parts["trajectory"] = trajectory
        group.add(trajectory)
        reveal.append("trajectory")
    if maths is not None:
        parts["maths"] = maths
        group.add(maths)
        reveal.append("maths")
    if reveal:
        beats.append(reveal)

    place(group, layout("title_stage_caption")[p.region])

    if p.beat == "swing_dodge":
        def act() -> Any:
            """Hero sweeps the pendulum arc over the orb; the orb lunges under him."""
            from manim import AnimationGroup, Arc, ApplyMethod, MoveAlongPath, Rotate

            a = anchor_dot.get_center()
            c = hero.get_center()
            v = c - a
            r_c = float(np.linalg.norm(v[:2]))
            phi = math.atan2(float(v[1]), float(v[0]))
            delta = -math.pi - 2.0 * phi
            if abs(delta) < 0.25:
                delta = -0.9 if float(v[0]) >= 0 else 0.9
            for _ in range(40):
                end = a + r_c * np.array([math.cos(phi + delta), math.sin(phi + delta), 0.0])
                if abs(float(end[0])) <= 6.3 and float(end[1]) >= -3.7:
                    break
                delta *= 0.85
            path = Arc(radius=r_c, start_angle=phi, angle=delta, arc_center=a)
            lunge = np.array([0.45 * (float(c[0]) - float(orb.get_center()[0])), 0.0, 0.0])
            return AnimationGroup(
                MoveAlongPath(hero, path),
                Rotate(web, angle=delta, about_point=a),
                ApplyMethod(orb.shift, lunge),
                run_time=2.2,
            )
    elif p.beat == "web_capture":
        def act() -> Any:
            """The web wraps the orb; its vibration decays and it shrinks slightly."""
            from manim import AnimationGroup, ApplyMethod, Create, ScaleInPlace, Succession, there_and_back

            jolts = [
                ApplyMethod(orb.shift, np.array([amp, 0.0, 0.0]), rate_func=there_and_back, run_time=0.16)
                for amp in (0.09, 0.055, 0.03)
            ]
            return Succession(
                Create(web, run_time=1.1),
                AnimationGroup(Succession(*jolts), ScaleInPlace(orb, 0.93), run_time=0.9),
            )
    elif p.beat == "chase":
        def act() -> Any:
            """The orb advances while turning; the hero flees on projectile hops."""
            from manim import AnimationGroup, ApplyMethod, MoveAlongPath, Rotate, Succession, VMobject

            h, o = hero.get_center(), orb.get_center()
            advance = 0.35 * float(o[0] - h[0])
            x0, y0 = float(h[0]), float(h[1])
            target = max(x0 - advance, -6.0)
            span = target - x0
            hop_h = abs(span) / 8.0
            points = []
            for hop in range(2):
                for i in range(13):
                    t = i / 12
                    points.append(np.array([x0 + span * (hop + t) / 2, y0 + 4 * hop_h * t * (1 - t), 0.0]))
            path = VMobject()
            path.set_points_smoothly(points)
            pursuit = Succession(
                ApplyMethod(orb.shift, np.array([-advance / 2, 0.0, 0.0])),
                Rotate(orb, angle=-math.tau / 6),
                ApplyMethod(orb.shift, np.array([-advance / 2, 0.0, 0.0])),
            )
            return AnimationGroup(MoveAlongPath(hero, path), pursuit, run_time=2.4)
    else:  # standoff
        def act() -> Any:
            """The hero breathes; the orb turns slowly. Nobody moves first."""
            from manim import AnimationGroup, Rotate, ScaleInPlace, there_and_back

            return AnimationGroup(
                ScaleInPlace(hero, 1.04, rate_func=there_and_back),
                Rotate(orb, angle=math.tau / 8),
                run_time=2.0,
            )

    return Built(group=group, parts=parts, beats=beats, motions=[act], notes="; ".join(notes))
