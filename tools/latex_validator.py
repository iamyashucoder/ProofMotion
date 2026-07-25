import re


def validate_latex(expression: str) -> dict[str, object]:
    balanced = expression.count("{") == expression.count("}") and expression.count("(") == expression.count(")")
    unsafe = bool(re.search(r"\\(input|write18|include|openout)", expression))
    return {"valid": balanced and not unsafe, "errors": ([] if balanced else ["unbalanced delimiters"]) + (["unsafe command"] if unsafe else [])}
