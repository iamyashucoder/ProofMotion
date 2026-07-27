"""Advanced JEE visual components: AC/EMI, optics, fluids, and chemistry."""

from __future__ import annotations

import math
from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.regions import layout, place


class ACPhasorParams(BaseModel):
    voltage: float = Field(default=100.0, gt=0)
    current: float = Field(default=5.0, gt=0)
    phase_deg: float = Field(default=45.0, ge=-90, le=90)
    region: str = "stage"


@component(version=1, domain="physics", params=ACPhasorParams)
def ac_phasor(p: ACPhasorParams) -> Built:
    """Voltage/current phasors with a signed phase difference for AC circuits."""
    import numpy as np
    from manim import DOWN, LEFT, RIGHT, UP, Angle, Arrow, Line, MathTex, VGroup

    origin = np.array([-1.2, -0.25, 0])
    axes = VGroup(Line(origin + LEFT * 2.4, origin + RIGHT * 3.0, color="#64748b"), Line(origin + DOWN * 2.3, origin + UP * 2.3, color="#64748b"))
    voltage = Arrow(origin, origin + RIGHT * 2.35, buff=0, color="#f87171", stroke_width=5)
    theta = math.radians(p.phase_deg)
    current_end = origin + np.array([2.05 * math.cos(theta), 2.05 * math.sin(theta), 0])
    current = Arrow(origin, current_end, buff=0, color="#38bdf8", stroke_width=5)
    phase = Angle(Line(origin, origin + RIGHT), Line(origin, current_end), radius=0.65, color="#fbbf24")
    labels = VGroup(MathTex(rf"V={p.voltage:g}\,\mathrm{{V}}", font_size=24, color="#f87171").next_to(voltage, UP, buff=0.1), MathTex(rf"I={p.current:g}\,\mathrm{{A}}", font_size=24, color="#38bdf8").next_to(current, UP, buff=0.1), MathTex(rf"\phi={p.phase_deg:g}^\circ", font_size=24, color="#fbbf24").next_to(phase, RIGHT, buff=0.1))
    parts: dict[str, Any] = {"axes": axes, "voltage_phasor": voltage, "current_phasor": current, "phase_angle": phase, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["axes"], ["voltage_phasor", "current_phasor", "phase_angle"], ["labels"]], notes="AC phasor diagram")


class InterferenceParams(BaseModel):
    wavelength_nm: float = Field(default=600.0, gt=0)
    slit_separation_mm: float = Field(default=0.5, gt=0)
    screen_distance_m: float = Field(default=2.0, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=InterferenceParams)
def double_slit_interference(p: InterferenceParams) -> Built:
    """Double-slit apparatus and bright fringes with computed fringe spacing."""
    from manim import DOWN, LEFT, RIGHT, UP, Line, MathTex, Rectangle, VGroup

    beta = p.wavelength_nm * 1e-9 * p.screen_distance_m / (p.slit_separation_mm * 1e-3)
    source = Rectangle(width=0.22, height=1.5, color="#fbbf24", fill_opacity=1).shift(LEFT * 4.6)
    barrier = Rectangle(width=0.18, height=3.2, color="#64748b", fill_opacity=1).shift(LEFT * 1.3)
    slits = VGroup(*[Rectangle(width=0.27, height=0.2, color="#0f172a", fill_opacity=1).move_to(LEFT * 1.3 + UP * y) for y in (-0.35, 0.35)])
    screen = Line(RIGHT * 4.0 + DOWN * 2.1, RIGHT * 4.0 + UP * 2.1, color="#e2e8f0", stroke_width=4)
    rays = VGroup(*[Line(source.get_right(), slit.get_left(), color="#fbbf24", stroke_width=2) for slit in slits], *[Line(slit.get_right(), screen.get_center(), color="#fbbf24", stroke_width=2) for slit in slits])
    fringes = VGroup(*[Line(RIGHT * 3.86 + UP * y, RIGHT * 4.14 + UP * y, color="#38bdf8" if index % 2 else "#f8fafc", stroke_width=8) for index, y in enumerate((-1.5, -1.0, -0.5, 0, 0.5, 1.0, 1.5))])
    label = MathTex(rf"\beta=\frac{{\lambda D}}{{d}}={beta * 1000:.2f}\,\mathrm{{mm}}", font_size=25).move_to(DOWN * 2.45)
    parts: dict[str, Any] = {"source": source, "barrier": barrier, "slits": slits, "screen": screen, "rays": rays, "fringes": fringes, "label": label}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["source", "barrier", "slits", "screen"], ["rays"], ["fringes", "label"]], notes=f"double slit fringe spacing {beta:g} m")


class DiffractionParams(BaseModel):
    wavelength_nm: float = Field(default=600.0, gt=0)
    slit_width_mm: float = Field(default=0.2, gt=0)
    screen_distance_m: float = Field(default=2.0, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=DiffractionParams)
def single_slit_diffraction(p: DiffractionParams) -> Built:
    """Single-slit central maximum and first-minimum relation a sin(theta)=lambda."""
    from manim import DOWN, LEFT, RIGHT, Axes, MathTex, Rectangle, VGroup

    first_minimum = p.wavelength_nm * 1e-9 * p.screen_distance_m / (p.slit_width_mm * 1e-3)
    slit = Rectangle(width=0.2, height=2.8, color="#64748b", fill_opacity=1).shift(LEFT * 4.0)
    opening = Rectangle(width=0.25, height=0.3, color="#0f172a", fill_opacity=1).move_to(slit)
    axes = Axes(x_range=[-4, 4, 1], y_range=[0, 1.2, 0.2], x_length=7.6, y_length=3.4, tips=False, axis_config={"include_numbers": False, "color": "#9aa7bd"}).shift(RIGHT * 1.0)
    pattern = axes.plot(lambda x: 1.0 if abs(x) < 1e-7 else (math.sin(math.pi * x) / (math.pi * x)) ** 2, x_range=[-4, 4], color="#fbbf24")
    label = MathTex(rf"a\sin\theta=\lambda,\quad y_1\approx\frac{{D\lambda}}{{a}}={first_minimum * 1000:.2f}\,\mathrm{{mm}}", font_size=22).next_to(axes, DOWN, buff=0.2)
    parts: dict[str, Any] = {"slit": slit, "opening": opening, "axes": axes, "pattern": pattern, "label": label}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["slit", "opening", "axes"], ["pattern"], ["label"]], notes="single slit diffraction pattern")


class FluidFlowParams(BaseModel):
    inlet_area: float = Field(default=2.0, gt=0)
    throat_area: float = Field(default=1.0, gt=0)
    inlet_speed: float = Field(default=2.0, gt=0)
    region: str = "stage"


@component(version=1, domain="physics", params=FluidFlowParams)
def fluid_flow_streamlines(p: FluidFlowParams) -> Built:
    """Venturi tube with streamlines and continuity-equation speed change."""
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, Line, MathTex, VGroup

    outlet_speed = p.inlet_area * p.inlet_speed / p.throat_area
    top = VGroup(Line(LEFT * 5 + [0, 1.35, 0], LEFT * 1.0 + [0, 1.35, 0], color="#94a3b8", stroke_width=5), Line(LEFT * 1 + [0, 1.35, 0], RIGHT * 1 + [0, 0.55, 0], color="#94a3b8", stroke_width=5), Line(RIGHT * 1 + [0, 0.55, 0], RIGHT * 5 + [0, 0.55, 0], color="#94a3b8", stroke_width=5))
    bottom = top.copy().flip(axis=RIGHT)
    streams = VGroup(*[Arrow(LEFT * 4.5 + [0, y, 0], RIGHT * 4.5 + [0, y * 0.45, 0], buff=0, color="#38bdf8", stroke_width=3) for y in (-0.9, -0.45, 0, 0.45, 0.9)])
    labels = VGroup(MathTex(r"A_1v_1=A_2v_2", font_size=27).move_to(UP * 2.0), MathTex(rf"v_2={outlet_speed:g}\,\mathrm{{m/s}}", font_size=24, color="#fbbf24").move_to(RIGHT * 1.2 + DOWN * 1.65))
    parts: dict[str, Any] = {"tube_top": top, "tube_bottom": bottom, "streamlines": streams, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["tube_top", "tube_bottom"], ["streamlines"], ["labels"]], notes="Venturi continuity visual")


class OrganicMechanismParams(BaseModel):
    step_label: str = "nucleophilic attack"
    region: str = "stage"


@component(version=1, domain="chemistry", params=OrganicMechanismParams)
def organic_mechanism_template(p: OrganicMechanismParams) -> Built:
    """Generic electron-pushing template; it deliberately does not predict products."""
    from manim import DOWN, LEFT, RIGHT, Arrow, MathTex, Text, VGroup

    nucleophile = MathTex(r":Nu^-", font_size=42, color="#38bdf8").shift(LEFT * 3.4)
    substrate = MathTex(r"R{-}C{=}O", font_size=42, color="#f8fafc")
    product = MathTex(r"R{-}C(O^-)Nu", font_size=40, color="#4ade80").shift(RIGHT * 3.4)
    electron_arrow = Arrow(nucleophile.get_right(), substrate.get_left(), buff=0.16, color="#fbbf24", stroke_width=4)
    reaction_arrow = Arrow(substrate.get_right() + RIGHT * 0.2, product.get_left() + LEFT * 0.2, buff=0.1, color="#e2e8f0", stroke_width=3)
    label = Text(p.step_label.upper(), font_size=21, color="#fbbf24").next_to(substrate, DOWN, buff=0.5)
    warning = Text("Template only — verify reagents and product with a chemistry reference.", font_size=16, color="#f87171").move_to(DOWN * 1.8)
    parts: dict[str, Any] = {"nucleophile": nucleophile, "substrate": substrate, "electron_arrow": electron_arrow, "reaction_arrow": reaction_arrow, "product_pattern": product, "label": label, "warning": warning}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["nucleophile", "substrate", "electron_arrow"], ["reaction_arrow", "product_pattern"], ["label", "warning"]], notes="generic organic electron-pushing template; not a reaction predictor")


class CoordinationParams(BaseModel):
    geometry: Literal["octahedral", "square_planar", "tetrahedral"] = "octahedral"
    region: str = "stage"


@component(version=1, domain="chemistry", params=CoordinationParams)
def coordination_complex(p: CoordinationParams) -> Built:
    """Coordination-complex geometry with a central metal and labelled ligands."""
    from manim import UP, Circle, Line, MathTex, VGroup

    points = {"octahedral": [(0, 1.8), (0, -1.8), (-1.8, 0), (1.8, 0), (-1.15, 1.05), (1.15, -1.05)], "square_planar": [(0, 1.7), (0, -1.7), (-1.7, 0), (1.7, 0)], "tetrahedral": [(0, 1.7), (-1.55, -0.9), (1.55, -0.9), (0, -1.65)]}[p.geometry]
    metal = Circle(radius=0.42, color="#fbbf24", fill_opacity=1)
    ligands = VGroup(*[Circle(radius=0.28, color="#a855f7", fill_opacity=0.85).move_to([x, y, 0]) for x, y in points])
    bonds = VGroup(*[Line(metal.get_center(), ligand.get_center(), color="#e2e8f0", stroke_width=3) for ligand in ligands])
    labels = VGroup(MathTex(r"M", font_size=28).move_to(metal), *[MathTex(r"L", font_size=22).move_to(ligand) for ligand in ligands])
    title = MathTex(rf"\text{{{p.geometry.replace('_', ' ')}}}", font_size=26).next_to(ligands, UP, buff=0.35)
    parts: dict[str, Any] = {"metal": metal, "bonds": bonds, "ligands": ligands, "labels": labels, "title": title}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["metal"], ["bonds", "ligands", "labels"], ["title"]], notes=f"coordination {p.geometry} geometry")


class VectorPlane3DParams(BaseModel):
    vector: list[float] = Field(default=[2.0, 1.0, 2.5], min_length=3, max_length=3)
    region: str = "stage"


@component(version=1, domain="linear_algebra", params=VectorPlane3DParams)
def vector_plane_3d(p: VectorPlane3DParams) -> Built:
    """Oblique 3D-style axes, plane, vector, and projection for vector/plane questions."""
    import numpy as np
    from manim import DOWN, LEFT, RIGHT, UP, Arrow, MathTex, Polygon, VGroup

    origin = np.array([-0.6, -1.0, 0])
    ex, ey, ez = RIGHT * 2.8, UP * 1.8 + RIGHT * 0.9, UP * 2.8
    axes = VGroup(Arrow(origin, origin + ex, buff=0, color="#f87171"), Arrow(origin, origin + ey, buff=0, color="#4ade80"), Arrow(origin, origin + ez, buff=0, color="#38bdf8"))
    plane = Polygon(origin + LEFT * 1.3 + DOWN * 0.25, origin + RIGHT * 2.2 + DOWN * 0.25, origin + RIGHT * 3.0 + UP * 1.35, origin + LEFT * 0.5 + UP * 1.35, color="#a855f7", fill_opacity=0.2)
    vx, vy, vz = p.vector
    endpoint = origin + RIGHT * (0.65 * vx + 0.25 * vy) + UP * (0.35 * vy + 0.52 * vz)
    vector = Arrow(origin, endpoint, buff=0, color="#fbbf24", stroke_width=5)
    projection = Arrow(origin, origin + RIGHT * (0.65 * vx + 0.25 * vy) + UP * (0.35 * vy), buff=0, color="#e2e8f0", stroke_width=3)
    drop = Arrow(endpoint, projection.get_end(), buff=0.06, color="#64748b", stroke_width=2)
    labels = VGroup(MathTex(r"x", font_size=22).next_to(axes[0], RIGHT, buff=0.08), MathTex(r"y", font_size=22).next_to(axes[1], UP, buff=0.08), MathTex(r"z", font_size=22).next_to(axes[2], UP, buff=0.08), MathTex(r"\vec v", font_size=25, color="#fbbf24").next_to(vector, UP, buff=0.1))
    parts: dict[str, Any] = {"plane": plane, "axes": axes, "vector": vector, "projection": projection, "drop": drop, "labels": labels}
    group = VGroup(*parts.values())
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["plane", "axes"], ["vector", "projection", "drop"], ["labels"]], notes="3D-style vector projection onto a plane")
