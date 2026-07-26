"""Differential equations, optimisation, and interpolation.

Symbolic first, numerical when symbolic gives out — which for differential
equations is most of the time, and is exactly why phase portraits and numerical
trajectories matter.
"""

from __future__ import annotations

from typing import Any, Literal

import numpy as np
import sympy as sp

from proofmotion.runtime.registry import ToolError, tool

MAX_POINTS = 4000


def _parse(expression: str) -> sp.Expr:
    from sympy.parsing.sympy_parser import (
        implicit_multiplication_application,
        parse_expr,
        standard_transformations,
    )

    try:
        return parse_expr(
            expression, transformations=(*standard_transformations, implicit_multiplication_application)
        )
    except (SyntaxError, TypeError, ValueError, AttributeError) as error:
        raise ToolError(f"could not parse {expression!r}: {error}") from error


@tool
def symbolic_ode(
    equation: str,
    function: str = "y",
    variable: str = "x",
    initial_conditions: dict | None = None,
) -> dict[str, Any]:
    """Solve an ordinary differential equation exactly, and verify the solution.

    The solution is substituted back into the equation before being returned, so
    a wrong branch is caught here rather than on screen.

    Args:
        equation: The ODE with the dependent function written plainly, e.g.
            "Derivative(y, x) + y" for y' + y = 0, or "Derivative(y,x,2) + y".
            Write it as an expression equal to zero.
        function: Name of the dependent function.
        variable: Name of the independent variable.
        initial_conditions: Optional, e.g. {"y(0)": 1, "Derivative(y, x)(0)": 0}.
    """
    x = sp.Symbol(variable)
    y = sp.Function(function)

    # Bind the *applied* function y(x), not the Function class. Mapping the bare
    # name to the class made "Derivative(y, x)" fail with "cannot represent
    # derivative of UndefinedFunction", so no ODE could be parsed at all.
    local = {function: y(x), variable: x, "Derivative": sp.Derivative, "diff": sp.diff}
    from sympy.parsing.sympy_parser import parse_expr

    try:
        expression = parse_expr(equation, local_dict=local)
    except (SyntaxError, TypeError, ValueError) as error:
        raise ToolError(f"could not parse the ODE {equation!r}: {error}") from error

    try:
        conditions = None
        if initial_conditions:
            # Conditions need the *class*: "y(0)" is a call, whereas the equation
            # needs the applied function. One binding cannot serve both.
            condition_local = {function: y, variable: x, "Derivative": sp.Derivative}
            conditions = {
                parse_expr(k, local_dict=condition_local): sp.nsimplify(v)
                for k, v in initial_conditions.items()
            }
        solution = sp.dsolve(sp.Eq(expression, 0), y(x), ics=conditions) if conditions else sp.dsolve(sp.Eq(expression, 0), y(x))
    except (NotImplementedError, ValueError, TypeError) as error:
        raise ToolError(f"sympy could not solve this ODE: {error}") from error

    solutions = solution if isinstance(solution, list) else [solution]
    verified = []
    for candidate in solutions:
        try:
            residual = sp.simplify(expression.subs(y(x), candidate.rhs).doit())
            verified.append(bool(residual == 0))
        except (TypeError, ValueError, AttributeError):
            verified.append(False)

    return {
        "equation": equation,
        "solutions": [str(s) for s in solutions],
        "latex": [sp.latex(s) for s in solutions],
        "substituted_back_to_zero": verified,
        "verified": all(verified) if verified else False,
    }


@tool
def numeric_ode(
    derivatives: list,
    initial_state: list,
    start: float,
    stop: float,
    variables: list | None = None,
    points: int = 200,
) -> dict[str, Any]:
    """Integrate a system of first-order ODEs numerically.

    Handles what dsolve cannot, and produces the trajectory a phase portrait or
    an animated solution curve needs.

    Args:
        derivatives: Right-hand sides, e.g. ["y", "-x"] for x'=y, y'=-x. Written
            in terms of the state variable names and t.
        initial_state: Value per state variable at `start`.
        start: Initial value of the independent variable.
        stop: Final value.
        variables: State variable names, defaulting to ["x", "y", "z"].
        points: How many samples to return.
    """
    from scipy.integrate import solve_ivp

    if len(derivatives) != len(initial_state):
        raise ToolError("one derivative per state variable is required")
    if not 2 <= points <= MAX_POINTS:
        raise ToolError(f"points must be between 2 and {MAX_POINTS}")

    names = variables or ["x", "y", "z"][: len(derivatives)]
    if len(names) != len(derivatives):
        raise ToolError("variables must match the number of derivatives")
    symbols = [sp.Symbol(n) for n in names]
    t = sp.Symbol("t")
    functions = [sp.lambdify([t, *symbols], _parse(str(d)), "numpy") for d in derivatives]

    def system(time, state):
        return [float(f(time, *state)) for f in functions]

    try:
        solved = solve_ivp(
            system, (start, stop), [float(v) for v in initial_state],
            t_eval=np.linspace(start, stop, points), rtol=1e-8, atol=1e-10,
        )
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ToolError(f"integration failed: {error}") from error
    if not solved.success:
        raise ToolError(f"integration did not converge: {solved.message}")

    trajectory = {name: [round(float(v), 8) for v in row] for name, row in zip(names, solved.y, strict=True)}
    return {
        "t": [round(float(v), 8) for v in solved.t],
        "trajectory": trajectory,
        "final_state": {n: trajectory[n][-1] for n in names},
        "points": len(solved.t),
    }


@tool
def numeric_optimize(
    objective: str,
    variables: list | None = None,
    guess: list | None = None,
    bounds: list | None = None,
    direction: Literal["minimize", "maximize"] = "minimize",
) -> dict[str, Any]:
    """Find a local optimum of an expression numerically.

    Args:
        objective: e.g. "(x-2)**2 + (y+1)**2".
        variables: Names, defaulting to the free symbols in order.
        guess: Starting point, one value per variable. Defaults to zeros.
        bounds: Optional [[low, high], ...] per variable.
        direction: minimize or maximize.
    """
    from scipy.optimize import minimize

    expression = _parse(objective)
    names = variables or sorted(str(s) for s in expression.free_symbols)
    if not names:
        raise ToolError("the objective has no variables to optimise over")
    symbols = [sp.Symbol(n) for n in names]
    sign = 1.0 if direction == "minimize" else -1.0
    function = sp.lambdify(symbols, expression, "numpy")

    start = [float(v) for v in (guess or [0.0] * len(names))]
    if len(start) != len(names):
        raise ToolError("guess must have one value per variable")

    try:
        result = minimize(
            lambda point: sign * float(function(*point)),
            start,
            bounds=[tuple(b) for b in bounds] if bounds else None,
        )
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ToolError(f"optimisation failed: {error}") from error

    return {
        "objective": objective,
        "direction": direction,
        "argument": {n: round(float(v), 8) for n, v in zip(names, result.x, strict=True)},
        "value": round(float(sign * result.fun), 8),
        "converged": bool(result.success),
        "message": str(result.message),
        "note": "a local optimum; global optimality is not claimed",
    }


@tool
def numeric_interpolate(
    x_values: list,
    y_values: list,
    at: list,
    kind: Literal["linear", "cubic", "nearest", "polynomial"] = "cubic",
) -> dict[str, Any]:
    """Interpolate between sampled points, and report the residual at the knots.

    Args:
        x_values: Sample positions, strictly increasing.
        y_values: Sample values.
        at: Positions to evaluate the interpolant at.
        kind: Interpolation scheme.
    """
    from scipy.interpolate import interp1d

    xs, ys = np.asarray(x_values, dtype=float), np.asarray(y_values, dtype=float)
    if xs.size != ys.size or xs.size < 2:
        raise ToolError("x_values and y_values must be the same length and hold at least two points")
    if np.any(np.diff(xs) <= 0):
        raise ToolError("x_values must be strictly increasing")

    if kind == "polynomial":
        coefficients = np.polyfit(xs, ys, deg=min(xs.size - 1, 10))
        evaluate = lambda points: np.polyval(coefficients, points)
        detail = {"coefficients": [round(float(c), 8) for c in coefficients]}
    else:
        if kind == "cubic" and xs.size < 4:
            raise ToolError("cubic interpolation needs at least four points")
        spline = interp1d(xs, ys, kind=kind, fill_value="extrapolate")
        evaluate = spline
        detail = {}

    values = [round(float(v), 8) for v in np.atleast_1d(evaluate(np.asarray(at, dtype=float)))]
    residual = float(np.max(np.abs(np.atleast_1d(evaluate(xs)) - ys)))
    return {
        "kind": kind,
        "at": list(at),
        "values": values,
        "max_error_at_knots": round(residual, 10),
        **detail,
    }
