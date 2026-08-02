from proofmotion.components.palette import activate
activate('dark')
from manim import *
import numpy as np

class GeneratedScene(ThreeDScene):
    def construct(self):
        # Background gradient
        def bg_func(p):
            x, y = p[0], p[1]
            r = np.sqrt(x*x + y*y)
            t = np.clip(r, 0, 1)
            return interpolate_color(BLUE_E, PURPLE_E, t)
        self.camera.set_background_from_func(bg_func)
        
        # Axes
        axes = ThreeDAxes(
            x_range=(-1.6, 1.6, 0.4),
            y_range=(-1.6, 1.6, 0.4),
            z_range=(0, 6.5, 1),
            x_length=6, y_length=6, z_length=6,
        )
        ...
