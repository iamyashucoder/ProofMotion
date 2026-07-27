"""Reusable 2D story objects for physics and educational motion scenes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from proofmotion.components.base import Built, component
from proofmotion.layout.regions import layout, place


def _bus(colour: str):
    from manim import DOWN, LEFT, RIGHT, UP, Circle, Rectangle, RoundedRectangle, VGroup

    body = RoundedRectangle(width=2.75, height=0.88, corner_radius=0.14, color=colour, fill_opacity=1)
    roof = RoundedRectangle(width=1.5, height=0.5, corner_radius=0.12, color=colour, fill_opacity=1)
    roof.next_to(body, UP, buff=-0.04).shift(LEFT * 0.12)
    windows = VGroup(*[Rectangle(width=0.31, height=0.27, color="#38bdf8", fill_opacity=0.9) for _ in range(4)])
    windows.arrange(RIGHT, buff=0.08).move_to(roof)
    wheels = VGroup(*[Circle(radius=0.22, color="#111827", fill_opacity=1) for _ in range(2)])
    wheels[0].move_to(body.get_left() + RIGHT * 0.55 + DOWN * 0.48)
    wheels[1].move_to(body.get_right() + LEFT * 0.55 + DOWN * 0.48)
    return VGroup(body, roof, windows, wheels)


def _car(colour: str):
    from manim import DOWN, LEFT, RIGHT, UP, Circle, Polygon, RoundedRectangle, VGroup

    body = RoundedRectangle(width=2.35, height=0.63, corner_radius=0.14, color=colour, fill_opacity=1)
    cabin = Polygon([-0.65, 0.31, 0], [-0.25, 0.8, 0], [0.65, 0.8, 0], [1.0, 0.31, 0],
                    color=colour, fill_opacity=1).move_to(body.get_center() + RIGHT * 0.02 + UP * 0.31)
    wheels = VGroup(*[Circle(radius=0.2, color="#111827", fill_opacity=1) for _ in range(2)])
    wheels[0].move_to(body.get_left() + RIGHT * 0.48 + DOWN * 0.37)
    wheels[1].move_to(body.get_right() + LEFT * 0.48 + DOWN * 0.37)
    return VGroup(body, cabin, wheels)


def _bicycle(colour: str, rider_colour: str = "#f97316"):
    from manim import LEFT, RIGHT, UP, Circle, Dot, Line, VGroup

    rear, front = LEFT * 0.62, RIGHT * 0.62
    wheels = VGroup(Circle(radius=0.31, color="#111827"), Circle(radius=0.31, color="#111827"))
    wheels[0].move_to(rear)
    wheels[1].move_to(front)
    frame = VGroup(Line(rear, UP * 0.42, color=colour, stroke_width=4), Line(UP * 0.42, front, color=colour, stroke_width=4),
                   Line(rear, front, color=colour, stroke_width=4), Line(UP * 0.42, UP * 0.87 + RIGHT * 0.12, color=colour, stroke_width=4))
    head = Dot(UP * 1.18 + RIGHT * 0.1, radius=0.13, color=rider_colour)
    torso = Line(UP * 1.04 + RIGHT * 0.08, UP * 0.7 + LEFT * 0.08, color=rider_colour, stroke_width=5)
    limbs = VGroup(Line(UP * 0.83 + LEFT * 0.03, UP * 0.56 + RIGHT * 0.36, color=rider_colour, stroke_width=4),
                   Line(UP * 0.72 + LEFT * 0.08, RIGHT * 0.2, color=rider_colour, stroke_width=4))
    return VGroup(wheels, frame, head, torso, limbs)


def _runner(colour: str, label: str = ""):
    from manim import DOWN, LEFT, RIGHT, UP, Circle, Line, Text, VGroup

    head = Circle(radius=0.15, color="#f5c2a8", fill_opacity=1).shift(UP * 0.85)
    body = Line(UP * 0.67, UP * 0.15, color=colour, stroke_width=6)
    arms = VGroup(Line(UP * 0.53, UP * 0.24 + LEFT * 0.37, color=colour, stroke_width=4),
                  Line(UP * 0.48, UP * 0.77 + RIGHT * 0.34, color=colour, stroke_width=4))
    legs = VGroup(Line(UP * 0.15, DOWN * 0.35 + LEFT * 0.32, color=colour, stroke_width=5),
                  Line(UP * 0.15, DOWN * 0.23 + RIGHT * 0.36, color=colour, stroke_width=5))
    person = VGroup(head, body, arms, legs)
    if label:
        person.add(Text(label, font_size=16, color=colour).next_to(head, UP, buff=0.08))
    return person


def _city():
    from manim import Rectangle, Text, VGroup

    heights = (1.1, 1.8, 1.35, 2.25, 1.55, 1.95, 1.2)
    buildings = VGroup()
    for index, height in enumerate(heights):
        building = Rectangle(width=0.72, height=height, color="#475569", fill_opacity=0.8, stroke_width=1)
        building.move_to([(index - 3) * 0.86, 1.55 - height / 2, 0])
        buildings.add(building)
    sign = Text("CITY", font_size=18, color="#cbd5e1").move_to(buildings[3].get_center())
    return VGroup(buildings, sign)


def _straight_road():
    from manim import WHITE, Line, Rectangle, VGroup

    asphalt = Rectangle(width=11, height=2.0, color="#64748b", fill_opacity=0.7, stroke_width=2)
    marks = VGroup(*[Line([x, 0, 0], [x + 0.7, 0, 0], color=WHITE, stroke_width=5) for x in (-5, -3.2, -1.4, 0.4, 2.2, 4.0)])
    return VGroup(asphalt, marks)


def _train(colour: str):
    from manim import DOWN, LEFT, RIGHT, Circle, Line, Rectangle, RoundedRectangle, VGroup

    engine = RoundedRectangle(width=1.65, height=0.82, corner_radius=0.12, color=colour, fill_opacity=1)
    cabin = Rectangle(width=0.42, height=0.4, color="#38bdf8", fill_opacity=0.9).move_to(engine.get_center() + RIGHT * 0.42 + DOWN * 0.02)
    carriages = VGroup(*[RoundedRectangle(width=1.45, height=0.72, corner_radius=0.1, color="#e2e8f0", fill_opacity=1) for _ in range(2)])
    carriages.arrange(LEFT, buff=0.08).next_to(engine, LEFT, buff=0.08)
    whole = VGroup(carriages, engine, cabin)
    wheels = VGroup(*[Circle(radius=0.13, color="#111827", fill_opacity=1) for _ in range(6)])
    for index, wheel in enumerate(wheels):
        wheel.move_to(whole.get_left() + RIGHT * (0.35 + index * 0.75) + DOWN * 0.47)
    rails = VGroup(Line(LEFT * 3.6 + DOWN * 0.67, RIGHT * 3.6 + DOWN * 0.67, color="#64748b", stroke_width=3),
                   Line(LEFT * 3.6 + DOWN * 0.9, RIGHT * 3.6 + DOWN * 0.9, color="#64748b", stroke_width=3))
    return VGroup(rails, whole, wheels)


def _airplane(colour: str):
    # LEFT and RIGHT were missing, so transport_story(vehicle="airplane")
    # raised NameError at build time — the only vehicle of the four that did.
    from manim import DOWN, LEFT, RIGHT, UP, Line, Polygon, VGroup

    fuselage = Line(LEFT * 1.5, RIGHT * 1.55, color=colour, stroke_width=12)
    nose = Polygon([1.55, 0, 0], [1.15, 0.25, 0], [1.15, -0.25, 0], color=colour, fill_opacity=1)
    wings = VGroup(Line(LEFT * 0.1, LEFT * 0.6 + UP * 0.9, color=colour, stroke_width=8),
                   Line(LEFT * 0.1, LEFT * 0.55 + DOWN * 0.85, color=colour, stroke_width=8),
                   Line(LEFT * 1.0, LEFT * 1.28 + UP * 0.43, color=colour, stroke_width=6))
    return VGroup(fuselage, nose, wings)


def _boat(colour: str):
    from manim import Line, Polygon, Rectangle, VGroup

    hull = Polygon([-1.45, 0, 0], [1.4, 0, 0], [0.9, -0.55, 0], [-0.85, -0.55, 0], color=colour, fill_opacity=1)
    cabin = Rectangle(width=0.7, height=0.4, color="#e2e8f0", fill_opacity=1).move_to([-0.1, 0.25, 0])
    mast = Line([0.65, 0, 0], [0.65, 1.15, 0], color="#cbd5e1", stroke_width=4)
    sail = Polygon([0.68, 1.08, 0], [0.68, 0.25, 0], [1.35, 0.25, 0], color="#38bdf8", fill_opacity=0.8)
    waves = VGroup(*[Line([x, -0.78, 0], [x + 0.55, -0.78, 0], color="#38bdf8", stroke_width=3) for x in (-2, -1, 0, 1, 2)])
    return VGroup(waves, hull, cabin, mast, sail)


def _rocket(colour: str):
    from manim import DOWN, RIGHT, UP, Polygon, Triangle, VGroup

    body = Polygon([-0.42, -0.8, 0], [0.42, -0.8, 0], [0.42, 0.55, 0], [0, 1.15, 0], [-0.42, 0.55, 0], color=colour, fill_opacity=1)
    window = Triangle(color="#38bdf8", fill_opacity=0.9).scale(0.22).move_to(UP * 0.35)
    fins = VGroup(Triangle(color="#f87171", fill_opacity=1).scale(0.35).rotate(-0.5).move_to(DOWN * 0.5 + RIGHT * 0.45),
                  Triangle(color="#f87171", fill_opacity=1).scale(0.35).rotate(0.5).move_to(DOWN * 0.5 + RIGHT * -0.45))
    flame = Polygon([-0.2, -0.82, 0], [0.2, -0.82, 0], [0, -1.45, 0], color="#fbbf24", fill_opacity=1)
    return VGroup(body, window, fins, flame)


def _tree():
    from manim import DOWN, UP, Circle, Rectangle, VGroup

    trunk = Rectangle(width=0.18, height=0.7, color="#92400e", fill_opacity=1).shift(DOWN * 0.35)
    leaves = VGroup(Circle(radius=0.35, color="#22c55e", fill_opacity=1).shift(UP * 0.3),
                    Circle(radius=0.28, color="#4ade80", fill_opacity=1).shift(UP * 0.5 + DOWN * 0.05))
    return VGroup(trunk, leaves)


def _house():
    from manim import UP, Polygon, Rectangle, VGroup

    base = Rectangle(width=1.25, height=0.9, color="#fbbf24", fill_opacity=0.9)
    roof = Polygon([-0.78, 0.45, 0], [0, 1.08, 0], [0.78, 0.45, 0], color="#ef4444", fill_opacity=1)
    door = Rectangle(width=0.25, height=0.46, color="#92400e", fill_opacity=1).shift(UP * -0.22)
    return VGroup(base, roof, door)


class TrafficStoryParams(BaseModel):
    vehicle: Literal["bus", "car", "bicycle"] = "bus"
    vehicle_color: str = "#fbbf24"
    show_city: bool = True
    region: str = "stage"


@component(version=1, domain="story", params=TrafficStoryParams)
def traffic_story(p: TrafficStoryParams) -> Built:
    """A 2D bus, car, or bicycle travelling on a city road."""
    from manim import VGroup

    vehicle = {"bus": _bus, "car": _car, "bicycle": _bicycle}[p.vehicle](p.vehicle_color)
    road = _straight_road().shift([0, -1.45, 0])
    vehicle.move_to([-1.2, -1.1, 0])
    parts: dict[str, Any] = {"road": road, "vehicle": vehicle}
    group = VGroup(road, vehicle)
    beats = [["road"], ["vehicle"]]
    if p.show_city:
        city = _city()
        parts["city"] = city
        group.add(city)
        beats.insert(0, ["city"])
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes=f"2D {p.vehicle} on a city road")


class TransportStoryParams(BaseModel):
    vehicle: Literal["train", "airplane", "boat", "rocket"] = "train"
    vehicle_color: str = "#f43f5e"
    region: str = "stage"


@component(version=1, domain="story", params=TransportStoryParams)
def transport_story(p: TransportStoryParams) -> Built:
    """A 2D train, airplane, boat, or rocket for motion-story animations."""
    from manim import VGroup

    vehicle = {"train": _train, "airplane": _airplane, "boat": _boat, "rocket": _rocket}[p.vehicle](p.vehicle_color)
    parts: dict[str, Any] = {"vehicle": vehicle}
    group = VGroup(vehicle)
    if p.vehicle in {"airplane", "rocket"}:
        city = _city().scale(0.72).shift([0, -2.0, 0])
        parts["city"] = city
        group.add(city)
    elif p.vehicle == "boat":
        trees = VGroup(_tree().scale(0.65).shift([-3.6, 0.2, 0]), _tree().scale(0.65).shift([3.6, 0.2, 0]))
        parts["shore_trees"] = trees
        group.add(trees)
    place(group, layout("title_stage_caption")[p.region])
    beats = [[key] for key in parts]
    return Built(group=group, parts=parts, beats=beats, notes=f"2D {p.vehicle} transport story")


class RoadSafetyParams(BaseModel):
    show_pedestrian: bool = True
    region: str = "stage"


@component(version=1, domain="story", params=RoadSafetyParams)
def road_safety_scene(p: RoadSafetyParams) -> Built:
    """A 2D road crossing with traffic light, car, pedestrian, trees and house."""
    from manim import DOWN, LEFT, RIGHT, UP, WHITE, Circle, Rectangle, VGroup

    road = _straight_road().shift(DOWN * 1.25)
    crossing = VGroup(*[Rectangle(width=0.28, height=1.35, color=WHITE, fill_opacity=0.9, stroke_width=0)
                        for _ in range(6)]).arrange(RIGHT, buff=0.16).move_to(DOWN * 1.25)
    car = _car("#ef4444").scale(0.8).move_to(LEFT * 2.9 + DOWN * 0.83)
    pole = Rectangle(width=0.12, height=1.5, color="#334155", fill_opacity=1).move_to(RIGHT * 4.1 + DOWN * 0.05)
    lights = VGroup(*[Circle(radius=0.11, color=colour, fill_opacity=1) for colour in ("#ef4444", "#fbbf24", "#22c55e")]).arrange(DOWN, buff=0.08)
    lights.next_to(pole, UP, buff=-0.68)
    house, tree = _house().scale(0.75).shift(LEFT * 3.9 + UP * 1.05), _tree().scale(0.8).shift(RIGHT * 2.8 + UP * 0.85)
    parts: dict[str, Any] = {"road": road, "crossing": crossing, "car": car, "traffic_light": VGroup(pole, lights), "house": house, "tree": tree}
    group = VGroup(*parts.values())
    beats = [["road", "crossing"], ["house", "tree"], ["car"], ["traffic_light"]]
    if p.show_pedestrian:
        walker = _runner("#7c3aed", "WALK").scale(0.72).move_to(DOWN * 0.85)
        parts["pedestrian"] = walker
        group.add(walker)
        beats.append(["pedestrian"])
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=beats, notes="2D road-safety crossing scene")


class PoliceChaseParams(BaseModel):
    road_turns: int = Field(default=4, ge=2, le=7)
    region: str = "stage"


@component(version=1, domain="story", params=PoliceChaseParams)
def police_bicycle_chase(p: PoliceChaseParams) -> Built:
    """A 2D police runner pursuing a bicycle thief on a zig-zag city road."""
    from manim import Line, VGroup

    city = _city()
    points = [[-5.1, -1.7, 0]]
    for index in range(p.road_turns):
        points.append([-3.4 + index * 1.75, -1.05 if index % 2 == 0 else -2.1, 0])
    points.append([4.9, -1.65, 0])
    path = VGroup(*[Line(points[index], points[index + 1], color="#94a3b8", stroke_width=18)
                    for index in range(len(points) - 1)])
    thief = _bicycle("#a855f7", "#f97316").scale(0.72).move_to([1.65, -1.05, 0])
    police = _runner("#2563eb", "POLICE").scale(0.86).move_to([-1.1, -1.25, 0])
    parts: dict[str, Any] = {"city": city, "zigzag_road": path, "thief_bicycle": thief, "police_runner": police}
    group = VGroup(city, path, thief, police)
    place(group, layout("title_stage_caption")[p.region])
    return Built(group=group, parts=parts, beats=[["city"], ["zigzag_road"], ["thief_bicycle"], ["police_runner"]],
                 notes="2D police-and-bicycle chase on a zig-zag road")
