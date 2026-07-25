from schemas.intent import AnimationIntent


def run_pedagogy_agent(intent: AnimationIntent, verified_math: dict) -> dict:
    strategy = "concrete-to-abstract" if intent.audience in {"beginner", "general"} else "definition-to-derivation"
    misconceptions = []
    if intent.topic == "gradient descent":
        misconceptions = ["Gradient descent is not guaranteed to find a global minimum in every problem.", "A larger learning rate is not always better."]
    return {"teaching_strategy": strategy, "introduce_example_before_abstraction": True, "misconceptions_to_avoid": misconceptions, "verified_math_available": verified_math["valid"]}
