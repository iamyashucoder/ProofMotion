"""Choose a renderer that can actually execute the requested scene."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RenderBackend = Literal["community", "community-opengl", "manimgl"]
RequestedBackend = Literal["auto", "community", "community-opengl", "manimgl"]


@dataclass(frozen=True)
class RenderChoice:
    backend: RenderBackend
    reason: str
    template: str | None = None


def choose_renderer(prompt: str, requested: RequestedBackend = "auto") -> RenderChoice:
    """Select the fastest compatible renderer, never merely the fastest one.

    ManimGL and Manim Community use different scene APIs.  The router only
    selects ManimGL when the request has a matching, authored ManimGL template;
    otherwise it chooses Community/OpenGL for GPU-heavy generated scenes.
    """
    text = prompt.casefold()
    if requested == "community":
        return RenderChoice("community", "requested Manim Community's validated default renderer")
    if requested == "community-opengl":
        return RenderChoice("community-opengl", "requested Manim Community's GPU-backed OpenGL renderer")
    is_rosette = "rosette" in text or "spirograph" in text or (
        "polar" in text and "24" in text and "25" in text
    )
    if is_rosette:
        return RenderChoice(
            backend="manimgl",
            template="advanced_polar_rosette.py",
            reason="matched the authored ManimGL polar-rosette template with glow and real-time tracing",
        )
    if "thomas attractor" in text or "thomas system" in text:
        return RenderChoice(
            backend="community-opengl",
            template="thomas_attractor.py",
            reason="matched the authored OpenGL Thomas-attractor template, avoiding dense 3D equation layout",
        )
    is_rolling_incline = "roll" in text and "inclined plane" in text and "sphere" in text
    if is_rolling_incline and ("two force" in text or "without slipping" in text):
        return RenderChoice(
            backend="community",
            template="rolling_sphere_incline.py",
            reason="matched the authored rolling-sphere template, which keeps force labels and derivation on separate beats",
        )
    if requested == "manimgl":
        return RenderChoice(
            "community-opengl",
            "no compatible ManimGL template exists; kept the generated scene on Community/OpenGL",
        )

    gpu_signals = ("3d", "surface", "vector field", "particle", "shader", "interactive", "camera orbit", "attractor")
    if any(signal in text for signal in gpu_signals):
        return RenderChoice("community-opengl", "detected a GPU-heavy 3D or field animation")
    return RenderChoice("community", "detected a standard generated mathematical animation")
