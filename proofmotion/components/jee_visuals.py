"""Reusable high-signal JEE Main/Advanced visual components.

Each component depicts a standard physical, chemical, or mathematical setup;
the derivation is then allowed to annotate a picture rather than replace one.
"""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.regions import layout, place


class RollingBodyParams(BaseModel):
    radius: float = Field(default=1.0, gt=0)
    angular_speed: float = Field(default=3.0, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=RollingBodyParams)
def rolling_body(p: RollingBodyParams) -> Built:
    """Rolling disc with translational and angular-velocity labels for rotation problems."""
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, Circle, Line, MathTex, VGroup

    floor = Line(LEFT * 5.2 + DOWN * 1.5, RIGHT * 5.2 + DOWN * 1.5, color="#94a3b8", stroke_width=4)
    disc = Circle(radius=1.15, color="#38bdf8", fill_opacity=0.28, stroke_width=4).shift(DOWN * 0.35)
    radius = Line(disc.get_center(), disc.get_bottom(), color="#fbbf24", stroke_width=3)
    spoke = Line(disc.get_center(), disc.get_center() + RIGHT * 0.88, color="#e2e8f0", stroke_width=3)
    velocity = Arrow(disc.get_top() + RIGHT * 0.15, disc.get_top() + RIGHT * 2.0, buff=0, color="#4ade80", stroke_width=4)
    tangent = Arrow(disc.get_right(), disc.get_right() + DOWN * 1.1, buff=0.08, color="#f87171", stroke_width=4)
    labels = VGroup(
        MathTex(rf"v=\omega R={p.angular_speed * p.radius:g}", font_size=25, color="#4ade80").next_to(velocity, UP, buff=0.12),
        MathTex(r"\omega", font_size=26, color="#f87171").next_to(tangent, RIGHT, buff=0.1),
        MathTex(r"R", font_size=24, color="#fbbf24").next_to(radius, LEFT, buff=0.1),
    )
    parts: dict[str, Any] = {"floor": floor, "disc": disc, "radius": radius, "spoke": spoke, "velocity": velocity, "angular_arrow": tangent, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["floor", "disc", "radius", "spoke"], ["velocity", "angular_arrow"], ["labels"]], notes="rolling without slipping: v=omega R")


class FluidColumnParams(BaseModel):
    density: float = Field(default=1000.0, gt=0)
    depth: float = Field(default=2.0, gt=0)
    gravity: float = Field(default=9.8, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=FluidColumnParams)
def fluid_column(p: FluidColumnParams) -> Built:
    """Fluid column with depth, pressure point, and hydrostatic-pressure relation."""
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, Line, MathTex, Rectangle, VGroup

    tank = Rectangle(width=3.2, height=3.6, color="#38bdf8", fill_opacity=0.2, stroke_width=3).shift(LEFT * 1.3)
    water = Rectangle(width=3.05, height=2.8, color="#0ea5e9", fill_opacity=0.45, stroke_width=0).move_to(tank.get_center() + DOWN * 0.38)
    surface = Line(water.get_left(), water.get_right(), color="#e0f2fe", stroke_width=3)
    point = Arrow(tank.get_right() + LEFT * 0.18 + DOWN * 0.8, tank.get_right() + RIGHT * 1.0 + DOWN * 0.8, buff=0, color="#f87171", stroke_width=4)
    depth_arrow = Arrow(surface.get_center() + RIGHT * 0.45, water.get_bottom() + RIGHT * 0.45, buff=0.06, color="#fbbf24", stroke_width=3)
    labels = VGroup(
        MathTex(r"h", font_size=27, color="#fbbf24").next_to(depth_arrow, RIGHT, buff=0.1),
        MathTex(r"P=P_0+\rho gh", font_size=29).move_to(RIGHT * 3.1 + UP * 0.55),
        MathTex(rf"\rho gh={p.density * p.gravity * p.depth:g}\,\mathrm{{Pa}}", font_size=22, color="#4ade80").move_to(RIGHT * 3.1 + DOWN * 0.25),
    )
    parts: dict[str, Any] = {"tank": tank, "fluid": water, "surface": surface, "pressure_arrow": point, "depth_arrow": depth_arrow, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["tank", "fluid", "surface"], ["depth_arrow", "pressure_arrow"], ["labels"]], notes="hydrostatic pressure rises linearly with depth")


class CapacitorPlatesParams(BaseModel):
    separation: float = Field(default=1.2, gt=0.2, le=2.5)
    voltage: float = Field(default=12.0, gt=0)
    dielectric: bool = False
    region: str = "stage"


@component(version=1, domain="physics", params=CapacitorPlatesParams)
def parallel_plate_capacitor(p: CapacitorPlatesParams) -> Built:
    """Parallel-plate capacitor with electric field, voltage, and optional dielectric."""
    from manim import LEFT, RIGHT, UP, Arrow, MathTex, Rectangle, Text, VGroup

    gap = p.separation * 1.35
    left_plate = Rectangle(width=0.18, height=3.2, color="#38bdf8", fill_opacity=1).shift(LEFT * gap / 2)
    right_plate = Rectangle(width=0.18, height=3.2, color="#f87171", fill_opacity=1).shift(RIGHT * gap / 2)
    charges = VGroup(*[Text("+", font_size=23, color="#38bdf8").move_to(left_plate.get_center() + UP * y + RIGHT * 0.22) for y in (-1, -0.35, 0.35, 1)], *[Text("−", font_size=23, color="#f87171").move_to(right_plate.get_center() + UP * y + LEFT * 0.22) for y in (-1, -0.35, 0.35, 1)])
    fields = VGroup(*[Arrow(left_plate.get_right() + UP * y, right_plate.get_left() + UP * y, buff=0.14, color="#fbbf24", stroke_width=3) for y in (-1, -0.35, 0.35, 1)])
    parts: dict[str, Any] = {"left_plate": left_plate, "right_plate": right_plate, "charges": charges, "field": fields}
    group = VGroup(left_plate, right_plate, charges, fields)
    if p.dielectric:
        slab = Rectangle(width=gap * 0.45, height=2.8, color="#a855f7", fill_opacity=0.35).move_to([0, 0, 0])
        parts["dielectric"] = slab
        group.add(slab)
    label = MathTex(rf"V={p.voltage:g}\,\mathrm{{V}},\quad E\approx V/d", font_size=27).next_to(group, UP, buff=0.28)
    parts["label"] = label
    group.add(label)
    place(group, layout("title_stage_caption")[p.region])
    beats = [["left_plate", "right_plate", "charges"], ["field"]]
    if p.dielectric:
        beats.append(["dielectric"])
    beats.append(["label"])
    return Built(group=group, parts=parts, beats=beats, notes="parallel-plate capacitor field and voltage")


class MagneticForceParams(BaseModel):
    charge_sign: Literal["positive", "negative"] = "positive"
    region: str = "stage"


@component(version=1, domain="physics", params=MagneticForceParams)
def magnetic_force_field(p: MagneticForceParams) -> Built:
    """Charged particle entering a uniform perpendicular magnetic field."""
    from manim import DOWN, LEFT, RIGHT, UP, Arc, Arrow, Dot, MathTex, Text, VGroup

    field = VGroup(*[Text("×", font_size=29, color="#64748b").move_to([x, y, 0]) for x in (-3, -2, -1, 0, 1, 2, 3) for y in (-1.4, -0.6, 0.2, 1.0)])
    particle = Dot(LEFT * 2.9 + DOWN * 0.95, radius=0.12, color="#f87171" if p.charge_sign == "positive" else "#38bdf8")
    path = Arc(radius=2.1, start_angle=-math.pi / 2, angle=math.pi / 2, color="#fbbf24", stroke_width=4).shift(LEFT * 0.8 + DOWN * 0.95)
    velocity = Arrow(particle.get_center(), particle.get_center() + RIGHT * 1.1, buff=0, color="#4ade80", stroke_width=4)
    force_direction = UP if p.charge_sign == "positive" else DOWN
    force = Arrow(particle.get_center(), particle.get_center() + force_direction * 0.85, buff=0, color="#a855f7", stroke_width=4)
    label = MathTex(r"\vec F=q\vec v\times\vec B", font_size=29).next_to(field, UP, buff=0.25)
    parts: dict[str, Any] = {"field_crosses": field, "particle": particle, "path": path, "velocity": velocity, "force": force, "label": label}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["field_crosses"], ["particle", "velocity", "force"], ["path", "label"]], notes=f"{p.charge_sign} charge in B into the page")


class EnergyLevelsParams(BaseModel):
    transition: Literal["hydrogen", "semiconductor"] = "hydrogen"
    region: str = "stage"


@component(version=1, domain="physics", params=EnergyLevelsParams)
def energy_levels(p: EnergyLevelsParams) -> Built:
    """Hydrogen-level transition or semiconductor band-gap diagram."""
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, Line, MathTex, Text, VGroup

    if p.transition == "hydrogen":
        lines = VGroup(*[Line(LEFT * 2.4 + UP * y, RIGHT * 0.5 + UP * y, color="#94a3b8", stroke_width=3) for y in (-1.4, -0.35, 0.45, 1.15)])
        names = VGroup(*[MathTex(rf"n={index}", font_size=22).next_to(line, RIGHT, buff=0.12) for index, line in zip((1, 2, 3, 4), lines, strict=True)])
        photon = Arrow(lines[3].get_center(), lines[0].get_center(), buff=0.12, color="#fbbf24", stroke_width=4)
        title = Text("HYDROGEN ENERGY LEVELS", font_size=23, color="#e2e8f0").next_to(lines, UP, buff=0.3)
        parts: dict[str, Any] = {"levels": lines, "level_labels": names, "transition": photon, "title": title}
    else:
        valence = Line(LEFT * 2.5 + DOWN * 0.9, RIGHT * 2.5 + DOWN * 0.9, color="#38bdf8", stroke_width=5)
        conduction = Line(LEFT * 2.5 + UP * 1.0, RIGHT * 2.5 + UP * 1.0, color="#f87171", stroke_width=5)
        excitation = Arrow(LEFT * 0.2 + DOWN * 0.78, LEFT * 0.2 + UP * 0.88, buff=0.08, color="#fbbf24", stroke_width=4)
        labels = VGroup(MathTex(r"E_g", font_size=27).next_to(excitation, RIGHT, buff=0.1), Text("CONDUCTION BAND", font_size=18, color="#f87171").next_to(conduction, UP, buff=0.15), Text("VALENCE BAND", font_size=18, color="#38bdf8").next_to(valence, DOWN, buff=0.15))
        parts = {"valence_band": valence, "conduction_band": conduction, "excitation": excitation, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[[key] for key in parts], notes=f"{p.transition} energy-level diagram")


class ReactionProfileParams(BaseModel):
    activation_energy: float = Field(default=60.0, gt=0)
    delta_h: float = Field(default=-25.0)
    region: str = "stage"


@component(version=1, domain="chemistry", params=ReactionProfileParams)
def reaction_energy_profile(p: ReactionProfileParams) -> Built:
    """Reaction-coordinate diagram with activation energy and enthalpy change."""
    from manim import DOWN, LEFT, RIGHT, Arrow, Axes, MathTex, VGroup

    axes = Axes(x_range=[0, 6, 1], y_range=[-2, 5, 1], x_length=8.1, y_length=3.8, tips=False, axis_config={"include_numbers": False, "color": "#9aa7bd"})
    reactant_y, peak_y = 0.0, 3.2
    product_y = reactant_y + (1 if p.delta_h > 0 else -1.15)
    curve = axes.plot(lambda x: reactant_y + (peak_y - reactant_y) * math.sin(math.pi * x / 6) ** 1.8 + (product_y - reactant_y) * x / 6, x_range=[0, 6], color="#fbbf24")
    ea = Arrow(axes.c2p(1.2, reactant_y), axes.c2p(1.2, peak_y), buff=0, color="#f87171", stroke_width=3)
    dh = Arrow(axes.c2p(5.0, reactant_y), axes.c2p(5.0, product_y), buff=0, color="#4ade80", stroke_width=3)
    labels = VGroup(MathTex(rf"E_a={p.activation_energy:g}\,\mathrm{{kJ/mol}}", font_size=23, color="#f87171").next_to(ea, LEFT, buff=0.1), MathTex(rf"\Delta H={p.delta_h:g}\,\mathrm{{kJ/mol}}", font_size=23, color="#4ade80").next_to(dh, RIGHT, buff=0.1), MathTex(r"\text{reaction coordinate}", font_size=23).next_to(axes, DOWN, buff=0.18))
    parts: dict[str, Any] = {"axes": axes, "profile": curve, "activation_arrow": ea, "enthalpy_arrow": dh, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["axes"], ["profile"], ["activation_arrow", "enthalpy_arrow", "labels"]], notes="reaction-coordinate energy profile")


class MolecularGeometryParams(BaseModel):
    shape: Literal["linear", "trigonal_planar", "tetrahedral"] = "tetrahedral"
    region: str = "stage"


@component(version=1, domain="chemistry", params=MolecularGeometryParams)
def molecular_geometry(p: MolecularGeometryParams) -> Built:
    """VSEPR-style molecular geometry for linear, trigonal-planar, or tetrahedral molecules."""
    from manim import UP, Circle, Line, MathTex, VGroup

    offsets = {"linear": [(-2.0, 0), (2.0, 0)], "trigonal_planar": [(0, 1.75), (-1.5, -1.1), (1.5, -1.1)], "tetrahedral": [(0, 1.85), (-1.65, -0.95), (1.65, -0.95), (0, -1.8)]}[p.shape]
    central = Circle(radius=0.38, color="#fbbf24", fill_opacity=1)
    atoms = VGroup(*[Circle(radius=0.28, color="#38bdf8", fill_opacity=0.9).move_to([x, y, 0]) for x, y in offsets])
    bonds = VGroup(*[Line(central.get_center(), atom.get_center(), color="#e2e8f0", stroke_width=4) for atom in atoms])
    title = MathTex(rf"\text{{{p.shape.replace('_', ' ')}}}", font_size=27).next_to(atoms, UP, buff=0.35)
    parts: dict[str, Any] = {"central_atom": central, "bonds": bonds, "outer_atoms": atoms, "title": title}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["central_atom"], ["bonds", "outer_atoms"], ["title"]], notes=f"VSEPR {p.shape}")


class ComplexPlaneParams(BaseModel):
    real: float = 2.0
    imaginary: float = 3.0
    region: str = "stage"


@component(version=1, domain="mathematics", params=ComplexPlaneParams)
def complex_plane_vector(p: ComplexPlaneParams) -> Built:
    """Argand-plane vector with real/imaginary projections, modulus, and argument."""
    from manim import UP, Arrow, Axes, DashedLine, Dot, MathTex, VGroup

    bound = max(3.0, abs(p.real) + 1, abs(p.imag) + 1)
    axes = Axes(x_range=[-bound, bound, 1], y_range=[-bound, bound, 1], x_length=6.5, y_length=4.5, tips=False, axis_config={"include_numbers": True, "font_size": 18, "color": "#9aa7bd"})
    end = axes.c2p(p.real, p.imag)
    vector = Arrow(axes.c2p(0, 0), end, buff=0, color="#fbbf24", stroke_width=4)
    point = Dot(end, color="#f87171")
    projections = VGroup(DashedLine(end, axes.c2p(p.real, 0), color="#64748b"), DashedLine(end, axes.c2p(0, p.imag), color="#64748b"))
    modulus = math.hypot(p.real, p.imag)
    label = MathTex(rf"z={p.real:g}{p.imag:+g}i,\quad |z|={modulus:.2f}", font_size=25).next_to(axes, UP, buff=0.2)
    parts: dict[str, Any] = {"axes": axes, "vector": vector, "point": point, "projections": projections, "label": label}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["axes"], ["vector", "point", "projections"], ["label"]], notes=f"complex number {p.real:g}{p.imag:+g}i")


class RootsOfUnityParams(BaseModel):
    order: int = Field(default=4, ge=2, le=12)
    radius: float = Field(default=2.0, gt=0.4, le=3.2)
    region: str = "stage"


@component(version=1, domain="mathematics", params=RootsOfUnityParams)
def roots_of_unity_polygon(p: RootsOfUnityParams) -> Built:
    """Argand plane with nth roots of unity as a labelled regular polygon."""
    from manim import UP, Circle, Dot, Line, MathTex, NumberPlane, VGroup

    plane = NumberPlane(
        x_range=[-3.5, 3.5, 1], y_range=[-3.0, 3.0, 1], x_length=6.4, y_length=4.7,
        background_line_style={"stroke_color": "#334155", "stroke_width": 1, "stroke_opacity": 0.55},
    )
    circle = Circle(radius=p.radius * (6.4 / 7.0), color="#64748b", stroke_width=2).move_to(plane.c2p(0, 0))
    points, spokes, labels = VGroup(), VGroup(), VGroup()
    centre = plane.c2p(0, 0)
    for index in range(p.order):
        angle = 2 * math.pi * index / p.order
        coordinate = plane.c2p(p.radius * math.cos(angle), p.radius * math.sin(angle))
        dot = Dot(coordinate, radius=0.07, color="#fbbf24")
        points.add(dot)
        spokes.add(Line(centre, coordinate, color="#475569", stroke_width=2))
        label = MathTex(rf"\omega^{index}", font_size=20, color="#e2e8f0").next_to(dot, coordinate - centre, buff=0.12)
        labels.add(label)
    polygon = VGroup(*[Line(points[index].get_center(), points[(index + 1) % p.order].get_center(), color="#a855f7", stroke_width=3) for index in range(p.order)])
    title = MathTex(rf"z^{p.order}=1", font_size=28, color="#4ade80").next_to(plane, UP, buff=0.18)
    parts: dict[str, Any] = {"axes": plane, "unit_circle": circle, "spokes": spokes, "polygon": polygon, "roots": points, "labels": labels, "equation": title}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["axes", "unit_circle"], ["spokes", "polygon", "roots"], ["labels", "equation"]], notes=f"{p.order} roots of unity on the Argand plane")
