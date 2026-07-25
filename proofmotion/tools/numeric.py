"""Numerical evaluation. Turns verified symbolic claims into plottable numbers.

Replaces tools/numerical_math.py's single hardcoded gradient_descent_sequence
with primitives that compose into it — and into anything else.
"""

from __future__ import annotations

from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

from proofmotion.runtime.registry import ToolError, tool

MAX_POINTS = 5000


def _callable(expression: str, variable: str):
    symbol = sp.Symbol(variable)
    try:
        return sp.lambdify(symbol, parse_expr(expression), "math")
    except (SyntaxError, TypeError, ValueError) as error:
        raise ToolError(f"Could not build a numeric function from {expression!r}: {error}") from error


@tool
def numeric_evaluate(expression: str, at: float, variable: str = "x") -> dict[str, Any]:
    """Evaluate an expression at a single point.

    Args:
        expression: e.g. "(x-2)**2 + 1".
        at: The value to substitute.
        variable: Name of the free variable.
    """
    try:
        value = float(_callable(expression, variable)(at))
    except (ArithmeticError, TypeError, ValueError) as error:
        raise ToolError(f"{expression} is not defined at {variable}={at}: {error}") from error
    return {"expression": expression, "at": at, "value": value}


@tool
def numeric_sample(expression: str, start: float, stop: float, count: int = 50, variable: str = "x") -> dict[str, Any]:
    """Sample an expression across an interval, for plotting or range-fitting.

    Also reports the observed min and max, which is what a sensible axis range
    should be built from rather than guessed.

    Args:
        expression: The function to sample.
        start: Interval start.
        stop: Interval end.
        count: Number of evenly spaced points.
        variable: Name of the free variable.
    """
    if count < 2 or count > MAX_POINTS:
        raise ToolError(f"count must be between 2 and {MAX_POINTS}, got {count}")
    fn = _callable(expression, variable)
    step = (stop - start) / (count - 1)
    xs, ys = [], []
    for i in range(count):
        x = start + i * step
        try:
            y = float(fn(x))
        except (ArithmeticError, TypeError, ValueError):
            continue  # a genuine singularity, not an error to hide
        xs.append(x)
        ys.append(y)
    if not ys:
        raise ToolError(f"{expression} produced no finite values on [{start}, {stop}]")
    return {
        "expression": expression,
        "x": xs,
        "y": ys,
        "y_min": min(ys),
        "y_max": max(ys),
        "skipped": count - len(ys),
    }


@tool
def numeric_iterate(update_rule: str, start: float, steps: int = 10, variable: str = "x") -> dict[str, Any]:
    """Iterate x <- update_rule(x) from a starting value, returning the trajectory.

    General enough to express gradient descent, Newton's method, fixed-point
    iteration, or any recurrence, without any of them being special-cased.

    Args:
        update_rule: Expression for the next value, e.g. "x - 0.2*2*(x-2)".
        start: Initial value.
        steps: Number of iterations.
        variable: Name of the iterated variable.
    """
    if steps < 1 or steps > 1000:
        raise ToolError(f"steps must be between 1 and 1000, got {steps}")
    fn = _callable(update_rule, variable)
    trajectory = [start]
    for _ in range(steps):
        try:
            nxt = float(fn(trajectory[-1]))
        except (ArithmeticError, TypeError, ValueError) as error:
            return {"rule": update_rule, "trajectory": trajectory, "diverged": True, "reason": str(error)}
        trajectory.append(nxt)
        if abs(nxt) > 1e12:
            return {"rule": update_rule, "trajectory": trajectory, "diverged": True, "reason": "magnitude overflow"}
    return {
        "rule": update_rule,
        "trajectory": trajectory,
        "diverged": False,
        "converged_to": trajectory[-1] if abs(trajectory[-1] - trajectory[-2]) < 1e-6 else None,
    }


@tool
def numeric_roots(expression: str, start: float, stop: float, variable: str = "x") -> dict[str, Any]:
    """Find real roots of an expression within an interval.

    Args:
        expression: e.g. "x**2 - 4".
        start: Interval start.
        stop: Interval end.
        variable: Name of the free variable.
    """
    symbol = sp.Symbol(variable)
    try:
        candidates = sp.solve(parse_expr(expression), symbol)
    except (NotImplementedError, TypeError, ValueError) as error:
        raise ToolError(f"Could not solve {expression!r}: {error}") from error
    roots = []
    for c in candidates:
        try:
            value = complex(c.evalf())
        except (TypeError, ValueError):
            continue
        if abs(value.imag) < 1e-9 and start <= value.real <= stop:
            roots.append(value.real)
    return {"expression": expression, "interval": [start, stop], "roots": sorted(roots)}
