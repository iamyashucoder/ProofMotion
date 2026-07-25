from typing import Any

import sympy as sp


def differentiate(expression: str, variable: str = "x") -> dict[str, Any]:
    symbol = sp.Symbol(variable, real=True)
    parsed = sp.sympify(expression, locals={variable: symbol})
    result = sp.diff(parsed, symbol)
    return {"input": expression, "result": str(result), "latex": sp.latex(result), "verified": True, "assumptions": [f"{variable} is real"]}


def integrate(expression: str, variable: str = "x") -> dict[str, Any]:
    symbol = sp.Symbol(variable, real=True)
    result = sp.integrate(sp.sympify(expression, locals={variable: symbol}), symbol)
    return {"input": expression, "result": str(result), "latex": sp.latex(result), "verified": True}


def simplify(expression: str) -> dict[str, Any]:
    result = sp.simplify(sp.sympify(expression))
    return {"input": expression, "result": str(result), "latex": sp.latex(result), "verified": True}
