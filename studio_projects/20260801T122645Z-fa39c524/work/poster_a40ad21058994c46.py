from proofmotion.components.palette import activate
activate('dark')
from manim import *
import numpy as np


class GeneratedScene(ThreeDScene):
    def construct(self):
        self.camera.background_color = "#0a0a2e"
        self.set_camera_orientation(phi=70 * DEGREES, theta=-45 * DEGREES)

        # ---------- Title (fixed in frame) ----------
        title = Text("Euler's Formula Visualized in 3D", font_size=36, color=WHITE)
        title.to_edge(UP, buff=0.25)
        self.add_fixed_in_frame_mobjects(title)

        # ---------- 3D axes: Re (x), Im (y), theta (z) ----------
        axes = ThreeDAxes(
            x_range=[-1.6, 1.6, 0.4],
            y_range=[-1.6, 1.6, 0.4],
            z_range=[0, 6.5, 1],
            x_length=4.5,
            y_length=4.5,
            z_length=5.0,
        )
        axes.set_color(BLUE_E)
        re_label = axes.get_x_axis_label(MathTex("\\text{Re}", color=TEAL))
        im_label = axes.get_y_axis_label(MathTex("\\text{Im}", color=TEAL))
        th_label = axes.get_z_axis_label(MathTex("\\theta", color=TEAL))

        # ---------- Unit circle in the complex plane ----------
        r = np.linalg.norm(axes.coords_to_point(1, 0, 0) - axes.coords_to_point(0, 0, 0))
        circle = Circle(radius=r, color=BLUE, stroke_width=3)

        # ---------- ValueTracker for theta ----------
        theta = ValueTracker(0)

        def P():
            t = theta.get_value()
            return axes.coords_to_point(np.cos(t), np.sin(t), t)

        def P0():
            t = theta.get_value()
            return axes.coords_to_point(np.cos(t), np.sin(t), 0)

        def radial_dir():
            p = P0() - axes.coords_to_point(0, 0, 0)
            n = np.linalg.norm(p)
            return p / n if n > 1e-6 else np.array([1.0, 0.0, 0.0])

        # ---------- Moving point, glow, radius, projections ----------
        point = always_redraw(lambda: Dot3D(P(), radius=0.09, color=GOLD))
        glow = always_redraw(lambda: Dot3D(P(), radius=0.24, color=GOLD, opacity=0.22))
        radius_vec = always_redraw(lambda: Line3D(
            axes.coords_to_point(0, 0, 0), P0(), color=GOLD, thickness=0.03))
        hproj = always_redraw(lambda: DashedLine(
            P0(), axes.coords_to_point(np.cos(theta.get_value()), 0, 0),
            color=PURE_CYAN, stroke_width=2))
        vproj = always_redraw(lambda: DashedLine(
            P0(), axes.coords_to_point(0, np.sin(theta.get_value()), 0),
            color=PURE_CYAN, stroke_width=2))
        cos_label = always_redraw(lambda: MathTex("\\cos\\theta", color=PURE_CYAN, font_size=26).move_to(
            axes.coords_to_point(np.cos(theta.get_value()), -0.42, 0)))
        sin_label = always_redraw(lambda: MathTex("\\sin\\theta", color=PURE_CYAN, font_size=26).move_to(
            axes.coords_to_point(-0.42, np.sin(theta.get_value()), 0)))

        # ---------- Helix (full path, revealed with Create) ----------
        helix = ParametricFunction(
            lambda t: axes.coords_to_point(np.cos(t), np.sin(t), t),
            t_range=[0, 2 * PI],
            color=BLUE,
            stroke_width=3,
        )

        # ---------- Complex number label (follows the point) ----------
        z_label = MathTex("z = \\cos\\theta + i\\sin\\theta", color=GOLD, font_size=30)
        z_label.move_to(axes.coords_to_point(1.25, 0.55, 0.3))

        # ---------- Angle highlight labels ----------
        def C(x, y, z):
            return axes.coords_to_point(x, y, z)

        ang_labels = VGroup(
            MathTex("e^{i0}=1", color=GOLD, font_size=26).move_to(C(1.35, 0.35, 0.2)),
            MathTex("e^{i\\pi/2}=i", color=GOLD, font_size=26).move_to(C(-0.35, 1.35, 1.8)),
            MathTex("e^{i\\pi}=-1", color=GOLD, font_size=26).move_to(C(-1.35, -0.35, 3.4)),
            MathTex("e^{i3\\pi/2}=-i", color=GOLD, font_size=26).move_to(C(0.35, -1.35, 5.0)),
            MathTex("e^{i2\\pi}=1", color=GOLD, font_size=26).move_to(C(1.35, 0.35, 6.6)),
        )

        # ---------- Euler's identity ----------
        euler_eq = MathTex("e^{i\\pi} + 1 = 0", color=GOLD, font_size=46)
        euler_eq.set_color_by_tex("e", GOLD)
        euler_eq.set_color_by_tex("i", PURE_CYAN)
        euler_eq.set_color_by_tex("\\pi", PURPLE)
        euler_eq.set_color_by_tex("1", TEAL)
        euler_eq.set_color_by_tex("0", RED)
        euler_eq.move_to(C(0, 0, 3.4))

        # ---------- Final text + boxed equation (fixed in frame) ----------
        final_text = Text(
            "Euler's Formula connects exponential growth, rotation,\ntrigonometry, and complex numbers.",
            font_size=28, color=WHITE, line_spacing=1.2,
        )
        final_text.to_edge(DOWN, buff=0.4)
        final_eq = MathTex("e^{i\\theta} = \\cos\\theta + i\\sin\\theta", color=GOLD, font_size=38)
        final_box = SurroundingRectangle(final_eq, color=GOLD, buff=0.2)
        final_group = VGroup(final_eq, final_box)
        final_group.next_to(final_text, UP, buff=0.3)

        # ================= PLAY 1: setup =================
        self.play(
            FadeIn(axes), FadeIn(re_label), FadeIn(im_label), FadeIn(th_label),
            Create(circle),
            run_time=1.2,
        )
        self.wait(0.3)

        # ================= PLAY 2: reveal point, radius, projections, complex number =================
        self.play(
            FadeIn(point), FadeIn(glow), Create(radius_vec),
            Create(hproj), Create(vproj),
            FadeIn(cos_label), FadeIn(sin_label),
            FadeIn(z_label),
            run_time=1.0,
        )
        self.wait(0.3)

        # reveal z = e^{i theta}
        z_label2 = MathTex("z = e^{i\\theta}", color=GOLD, font_size=30)
        self.play(TransformMatchingTex(z_label, z_label2), run_time=0.8)
        z_label2.add_updater(lambda m: m.move_to(P0() + 0.6 * radial_dir() + OUT * 0.3))
        self.wait(0.2)

        # ================= PLAY 3: rotate 0 -> 2pi, trace helix =================
        self.play(
            theta.animate.set_value(2 * PI),
            Create(helix),
            run_time=3.5,
        )
        self.wait(0.3)

        # ================= PLAY 4: angle highlights =================
        self.play(*[FadeIn(l, scale=0.6) for l in ang_labels], run_time=1.5)
        self.wait(0.3)

        # ================= PLAY 5: Euler's identity =================
        self.play(
            FadeOut(ang_labels[2]),
            FadeIn(euler_eq, scale=0.7),
            run_time=1.8,
        )
        self.wait(0.4)

        # ================= PLAY 6: final pull-back + text + boxed equation =================
        self.play(
            self.move_camera(phi=60 * DEGREES, theta=-30 * DEGREES, zoom=0.72, run_time=2.5),
            FadeIn(final_text),
            FadeIn(final_group),
            run_time=2.5,
        )
        self.wait(1.0)
