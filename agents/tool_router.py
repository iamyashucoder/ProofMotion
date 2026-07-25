from schemas.intent import AnimationIntent


def select_tools(intent: AnimationIntent, math_plan: dict) -> list[str]:
    tools = ["latex_validator", "code_validator", "manim_renderer", "live_preview"]
    if math_plan.get("requires_symbolic_math"):
        tools.append("sympy_verify")
    if intent.requires_numerical_simulation:
        tools.append("numerical_sequence")
    if intent.requires_graph:
        tools.append("function_graph_template")
    return tools
