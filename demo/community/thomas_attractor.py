"""OpenGL-ready Thomas attractor scene without fragile equation stacking."""

from __future__ import annotations

import numpy as np
from manim import BLUE, DEGREES, GREEN, RED, UL, Create, FadeIn, Text, ThreeDAxes, ThreeDScene, VMobject


class GeneratedScene(ThreeDScene):
    """Numerically integrate and present the Thomas attractor in a clean 3D view."""

    @staticmethod
    def _step(state: np.ndarray, dt: float, damping: float = 0.2) -> np.ndarray:
        def field(value: np.ndarray) -> np.ndarray:
            x, y, z = value
            return np.array((np.sin(y) - damping * x, np.sin(z) - damping * y, np.sin(x) - damping * z))

        k1 = field(state)
        k2 = field(state + 0.5 * dt * k1)
        k3 = field(state + 0.5 * dt * k2)
        k4 = field(state + dt * k3)
        return state + dt * (k1 + 2 * k2 + 2 * k3 + k4) / 6

    def construct(self) -> None:
        dt = 0.04
        state = np.array((0.1, 0.0, 0.0))
        samples: list[np.ndarray] = []
        for index in range(5_000):
            state = self._step(state, dt)
            if index > 350 and index % 2 == 0:
                samples.append(state.copy())

        axes = ThreeDAxes(
            x_range=(-4.5, 4.5, 1), y_range=(-4.5, 4.5, 1), z_range=(-4.5, 4.5, 1),
            x_length=7, y_length=7, z_length=7,
        )
        path = VMobject(stroke_width=2.2)
        path.set_points_as_corners([axes.c2p(*point) for point in samples])
        path.set_color_by_gradient(BLUE, GREEN, RED)

        title = Text("Thomas Attractor", font_size=40).to_corner(UL)
        subtitle = Text("dx/dt = sin(y) − 0.2x   •   bounded, aperiodic flow", font_size=22).next_to(title, direction=-UL)
        self.add_fixed_in_frame_mobjects(title, subtitle)
        self.set_camera_orientation(phi=68 * DEGREES, theta=-48 * DEGREES)
        self.play(FadeIn(title), FadeIn(subtitle), Create(axes), run_time=1.3)
        self.play(Create(path), run_time=7)
        self.begin_ambient_camera_rotation(rate=0.12)
        self.wait(4)
