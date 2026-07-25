from manim import *

class GeneratedScene(Scene):
    def construct(self):
        # 1. Setup Axes and Function
        axes = Axes(
            x_range=[-1, 5, 1],
            y_range=[-1, 4, 1],
            axis_config={"include_numbers": True},
            tips=False
        )
        
        # Parabola function: f(x) = 0.5 * (x-2)^2 + 0.5
        # Minimum is at x=2, y=0.5
        func = axes.plot(lambda x: 0.5 * (x - 2)**2 + 0.5, x_range=[0, 4], color=BLUE)
        
        labels = axes.get_axis_labels(
            x_label=MathTex("x"),
            y_label=MathTex("Cost")
        )

        self.play(Create(axes), Write(labels))
        self.play(Create(func))
        self.wait(1)

        # 2. Gradient Descent Setup
        # Starting point: x = 0.5
        start_x = 0.5
        start_y = 0.5 * (start_x - 2)**2 + 0.5
        
        dot = Dot(color=RED)
        dot.move_to(axes.c2p(start_x, start_y))
        
        # Text explanation
        title = Text("Gradient Descent", font_size=36).to_edge(UP)
        desc = Text("Minimize the cost function", font_size=24, color=GRAY).next_to(title, DOWN)
        
        self.play(Write(title), Write(desc))
        self.play(FadeIn(dot))
        self.wait(1)

        # 3. Animation Loop
        # We will simulate steps: x_new = x_old - learning_rate * derivative
        # f'(x) = x - 2
        # Let's pick a learning rate of 0.5 for visual clarity
        learning_rate = 0.5
        current_x = start_x
        
        # Create a vector to represent the gradient (slope)
        gradient_vector = always_redraw(lambda: 
            Arrow(
                start=axes.c2p(current_x, 0.5 * (current_x - 2)**2 + 0.5),
                end=axes.c2p(current_x, 0.5 * (current_x - 2)**2 + 0.5 + (current_x - 2)),
                color=YELLOW,
                buff=0
            )
        )
        
        slope_label = Text("Gradient (Slope)", font_size=20, color=YELLOW).next_to(gradient_vector, RIGHT, buff=0.1)

        self.play(Create(gradient_vector), Write(slope_label))
        self.wait(1)

        # Iterations
        steps = 6
        for _ in range(steps):
            # Calculate derivative at current x
            derivative = current_x - 2
            
            # Update current_x
            # We use a small step for smooth animation
            target_x = current_x - learning_rate * derivative
            
            # Animate the dot moving to the new position
            # We use a ValueTracker to make the movement smooth
            tracker = ValueTracker(current_x)
            
            # Redefine dot to follow tracker
            moving_dot = always_redraw(lambda: 
                Dot(color=RED).move_to(axes.c2p(tracker.get_value(), 0.5 * (tracker.get_value() - 2)**2 + 0.5))
            )
            
            # Redefine gradient vector to follow tracker
            moving_gradient = always_redraw(lambda: 
                Arrow(
                    start=axes.c2p(tracker.get_value(), 0.5 * (tracker.get_value() - 2)**2 + 0.5),
                    end=axes.c2p(tracker.get_value(), 0.5 * (tracker.get_value() - 2)**2 + 0.5 + (tracker.get_value() - 2)),
                    color=YELLOW,
                    buff=0
                )
            )

            self.add(moving_dot, moving_gradient)
            self.play(
                tracker.animate.set_value(target_x),
                run_time=1.5,
                rate_func=linear
            )
            current_x = target_x

        # 4. Conclusion
        final_text = Text("Minimum reached!", font_size=30, color=GREEN).to_edge(DOWN, buff=0.5)
        self.play(Write(final_text))
        
        # Highlight the minimum point
        min_dot = Dot(color=GREEN, radius=0.1)
        min_dot.move_to(axes.c2p(2, 0.5))
        self.play(Create(min_dot))
        
        self.wait(2)