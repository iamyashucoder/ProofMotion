from schemas.intent import AnimationIntent
from schemas.storyboard import Storyboard, StoryboardScene


def run_visual_director(intent: AnimationIntent, verified_math: dict, pedagogy_plan: dict) -> Storyboard:
    if intent.topic == "gradient descent":
        scenes = [
            StoryboardScene(scene_id="intro", purpose="Name the optimization task.", duration_seconds=4, narration="We want to minimize a loss function.", visual_objects=[{"type": "title", "content": "Gradient Descent"}]),
            StoryboardScene(scene_id="loss", purpose="Show the objective and starting parameter.", duration_seconds=7, narration="The red point is our current parameter value on the loss curve.", visual_objects=[{"type": "axes"}, {"type": "function_graph", "equation": "(x-2)^2+1"}, {"type": "moving_point"}], equations=["f(x)=(x-2)^2+1"]),
            StoryboardScene(scene_id="slope", purpose="Connect a tangent slope to the update.", duration_seconds=8, narration="The derivative points uphill, so the update moves in the opposite direction.", visual_objects=[{"type": "tangent_line"}, {"type": "slope_arrow"}], equations=["x_{t+1}=x_t-\\eta f'(x_t)"]),
            StoryboardScene(scene_id="convergence", purpose="Animate verified numerical iterations.", duration_seconds=11, narration="Repeated updates approach the minimum when the learning rate is suitable.", visual_objects=[{"type": "trajectory"}, {"type": "minimum_marker"}], equations=["x_t\\to2"]),
        ]
    else:
        scenes = [StoryboardScene(scene_id="intro", purpose=intent.educational_goal, duration_seconds=float(intent.duration_seconds), narration=intent.educational_goal, visual_objects=[{"type": "title", "content": intent.topic}])]
    return Storyboard(teaching_strategy=pedagogy_plan["teaching_strategy"], scenes=scenes, live_edit_controls=["change scene duration", "edit narration", "toggle equations", "adjust graph range", "change camera/layout notes"])
