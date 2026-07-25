from schemas.intent import AnimationIntent
from schemas.math_plan import MathStep, MathematicalPlan


def run_math_planner(intent: AnimationIntent) -> MathematicalPlan:
    if intent.topic == "gradient descent":
        steps = [
            MathStep(index=1, concept="objective function", equation_latex="f(x)=(x-2)^2+1", explanation="Use a convex function with a visible minimum at x=2."),
            MathStep(index=2, concept="local slope", equation_latex="f'(x)=2(x-2)", explanation="The derivative gives the direction of steepest local increase."),
            MathStep(index=3, concept="update rule", equation_latex="x_{t+1}=x_t-\\eta f'(x_t)", explanation="Move opposite the derivative with a small positive learning rate."),
            MathStep(index=4, concept="convergence", equation_latex="x_t\\to2", explanation="For a suitable learning rate, the iterates approach the minimum."),
        ]
        return MathematicalPlan(topic=intent.topic, concept_sequence=steps, requires_symbolic_math=True, requires_numerical_simulation=True)
    if intent.topic == "derivative":
        return MathematicalPlan(topic=intent.topic, concept_sequence=[
            MathStep(index=1, concept="function", equation_latex="y=f(x)", explanation="Start from a smooth curve."),
            MathStep(index=2, concept="average rate", equation_latex="\\frac{f(x+\\Delta x)-f(x)}{\\Delta x}", explanation="A secant slope compares two nearby points."),
            MathStep(index=3, concept="limit", equation_latex="f'(x)=\\lim_{\\Delta x\\to0}\\frac{f(x+\\Delta x)-f(x)}{\\Delta x}", explanation="Shrinking the interval produces the tangent slope."),
        ], requires_symbolic_math=False)
    if intent.topic == "definite integration":
        return MathematicalPlan(topic=intent.topic, concept_sequence=[
            MathStep(index=1, concept="partition", equation_latex="\\Delta x", explanation="Split the interval into thin pieces."),
            MathStep(index=2, concept="Riemann sum", equation_latex="\\sum f(x_i)\\Delta x", explanation="Add the small rectangular contributions."),
            MathStep(index=3, concept="definite integral", equation_latex="\\int_a^b f(x)\\,dx", explanation="The limit of the sum is accumulated signed area."),
        ])
    return MathematicalPlan(topic=intent.topic, concept_sequence=[MathStep(index=1, concept="concrete example", explanation=intent.educational_goal, requires_verification=False)])
