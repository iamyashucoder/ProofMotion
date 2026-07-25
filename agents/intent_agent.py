from schemas.intent import AnimationIntent


def run_intent_agent(user_prompt: str) -> AnimationIntent:
    prompt = user_prompt.lower()
    if "gradient descent" in prompt:
        return AnimationIntent(topic="gradient descent", domain="optimization", audience="beginner" if "beginner" in prompt else "general", educational_goal="Explain iterative movement toward a minimum using slope and a learning rate.", duration_seconds=30, difficulty="introductory", requires_graph=True, requires_numerical_simulation=True)
    if any(word in prompt for word in ("derivative", "differentiat")):
        return AnimationIntent(topic="derivative", domain="calculus", educational_goal="Explain instantaneous rate of change with a tangent line.", duration_seconds=30, difficulty="introductory", requires_graph=True, requires_derivation=True)
    if any(word in prompt for word in ("integral", "integration", "riemann")):
        return AnimationIntent(topic="definite integration", domain="calculus", educational_goal="Explain accumulated area under a single-variable function.", duration_seconds=35, difficulty="introductory", requires_graph=True, requires_derivation=False, assumptions=["Interpret integration as a single-variable definite integral."])
    if any(word in prompt for word in ("triangle", "pythagoras", "geometry")):
        return AnimationIntent(topic="basic geometry", domain="geometry", educational_goal="Explain a geometric relationship with labeled shapes.", duration_seconds=25, difficulty="introductory")
    return AnimationIntent(topic=user_prompt.strip(), domain="general mathematics", educational_goal="Create a clear introductory visual explanation.", duration_seconds=25, difficulty="introductory", clarification_needed="The request is broad; the first draft will use one concrete example.")
