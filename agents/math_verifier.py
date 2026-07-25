from schemas.math_plan import MathematicalPlan
from tools.latex_validator import validate_latex
from tools.symbolic_math import differentiate


def run_math_verifier(plan: MathematicalPlan) -> dict:
    results = []
    for step in plan.concept_sequence:
        validation = validate_latex(step.equation_latex or "")
        results.append({"step": step.index, "equation_latex": step.equation_latex, "valid": validation["valid"], "errors": validation["errors"], "kind": "pedagogical claim"})
    if plan.topic == "gradient descent":
        derivative = differentiate("(x-2)**2 + 1")
        results[1].update({"kind": "exact symbolic result", "symbolic": derivative, "expected_latex": "2(x-2)"})
    return {"valid": all(item["valid"] for item in results), "checks": results}
