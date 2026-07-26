"""Verification: checking that a result is *right*, not merely that it exists.

Solving and being correct are different acts. `verify_plan` previously checked
that LaTeX compiled and that single-`=` claims survived sympy — which on a
derivative-from-first-principles run proved exactly zero of ten steps, because
every step was a limit and nothing was mechanically checkable.

These tools cover the ways a claim can actually be wrong: inconsistent units, a
counterexample, wrong behaviour in a limiting case, an implausible sign or
magnitude, an assumption that does not hold, a broken inductive step, or a
symmetry the result should respect and does not.

Refutation comes first everywhere here. Finding one counterexample is cheap and
conclusive; proving a general claim is neither.
"""

from __future__ import annotations

import math
import random
from typing import Any

import sympy as sp
from sympy.parsing.sympy_parser import parse_expr

from proofmotion.runtime.registry import ToolError, tool

SAMPLES = 200
TOLERANCE = 1e-9


def _parse(expression: str) -> sp.Expr:
    try:
        return parse_expr(expression, evaluate=True)
    except (SyntaxError, TypeError, ValueError, AttributeError) as error:
        raise ToolError(f"could not parse {expression!r}: {error}") from error


def _sides(claim: str) -> tuple[sp.Expr, sp.Expr, str]:
    """Split a claim into (left, right, relation)."""
    for token, name in (("<=", "<="), (">=", ">="), ("==", "="), ("=", "="), ("<", "<"), (">", ">")):
        if token in claim:
            left, _, right = claim.partition(token)
            return _parse(left), _parse(right), name
    raise ToolError(f"{claim!r} states no relation; expected =, <, >, <= or >=")


def _holds(relation: str, difference: float) -> bool:
    if relation == "=":
        return abs(difference) <= 1e-7
    if relation == "<":
        return difference < 0
    if relation == "<=":
        return difference <= 1e-9
    if relation == ">":
        return difference > 0
    return difference >= -1e-9


@tool
def units_check(left: str, right: str, dimensions: dict) -> dict[str, Any]:
    """Check that two sides of a physical equation have the same dimensions.

    The cheapest way to catch a wrong physics formula. F = m*a passes;
    F = m*v does not, whatever the numbers say.

    Args:
        left: Left side, e.g. "F".
        right: Right side, e.g. "m*a".
        dimensions: Dimension per symbol, e.g. {"F": "force", "m": "mass",
            "a": "acceleration"}. Use SI dimension names: length, mass, time,
            velocity, acceleration, force, energy, power, pressure, charge,
            current, voltage, frequency, momentum, area, volume.
    """
    import sympy.physics.units.definitions.dimension_definitions as named
    from sympy.physics.units.systems.si import dimsys_SI

    def resolve(name: str) -> Any:
        """A real named dimension, not an opaque symbol.

        Wrapping the name in Dimension(Symbol(name)) produced something that
        never reduced to base dimensions, so nothing could disagree with
        anything: F = m*v was reported consistent.
        """
        dimension = getattr(named, name, None)
        if dimension is None or not hasattr(dimension, "name"):
            available = sorted(n for n in dir(named) if not n.startswith("_") and hasattr(getattr(named, n), "name"))
            raise ToolError(f"unknown dimension {name!r}. Available: {', '.join(available)}")
        return dimension

    # Force every named symbol to be a plain Symbol. Physics writes E for energy
    # and I for current, and sympy reads those as Euler's number and the
    # imaginary unit — so "E = m*c**2" arrived with no free symbols at all and
    # measured as dimensionless.
    local = {name: sp.Symbol(name) for name in dimensions}

    def dimension_of(side: str) -> Any:
        try:
            expression = parse_expr(side, local_dict=local, evaluate=True)
        except (SyntaxError, TypeError, ValueError) as error:
            raise ToolError(f"could not parse {side!r}: {error}") from error
        substitutions = {}
        for symbol in expression.free_symbols:
            key = str(symbol)
            if key not in dimensions:
                raise ToolError(f"no dimension given for {key!r}; supply one for every symbol")
            substitutions[symbol] = resolve(dimensions[key])
        return expression.subs(substitutions)

    left_dim, right_dim = dimension_of(left), dimension_of(right)
    # Compare exponents over base dimensions; that is the only comparison that
    # distinguishes force from mass*velocity.
    left_base = dimsys_SI.get_dimensional_dependencies(left_dim)
    right_base = dimsys_SI.get_dimensional_dependencies(right_dim)
    consistent = left_base == right_base

    def readable(base: dict) -> str:
        return " * ".join(f"{str(d).replace('Dimension(', '').split(',')[0].rstrip(')')}^{e}" for d, e in base.items()) or "dimensionless"

    return {
        "claim": f"{left} = {right}",
        "consistent": consistent,
        "left_dimension": readable(left_base),
        "right_dimension": readable(right_base),
        "verdict": "dimensionally consistent" if consistent else "DIMENSIONAL MISMATCH — the formula is wrong",
    }


@tool
def counterexample_search(claim: str, low: float = -10.0, high: float = 10.0, samples: int = SAMPLES) -> dict[str, Any]:
    """Try to refute a claimed identity or inequality by sampling.

    Run this before attempting to prove anything. A counterexample settles the
    question immediately; failing to find one is evidence, not proof, and the
    result says so.

    Args:
        claim: e.g. "(x+1)**2 = x**2 + 2*x + 1" or "x**2 >= x".
        low: Lower bound of the sampling range.
        high: Upper bound of the sampling range.
        samples: How many random points to try.
    """
    left, right, relation = _sides(claim)
    symbols = sorted(left.free_symbols | right.free_symbols, key=str)
    if not symbols:
        difference = float(sp.N(left - right))
        return {
            "claim": claim,
            "refuted": not _holds(relation, difference),
            "counterexample": None if _holds(relation, difference) else {"difference": difference},
            "note": "no free symbols; evaluated directly",
        }

    rng = random.Random(0)
    for _ in range(max(1, samples)):
        point = {s: rng.uniform(low, high) for s in symbols}
        try:
            difference = complex(sp.N((left - right).subs(point)))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(difference.imag) > 1e-9:
            continue
        if not _holds(relation, difference.real):
            return {
                "claim": claim,
                "refuted": True,
                "counterexample": {str(s): round(v, 6) for s, v in point.items()},
                "difference": round(difference.real, 9),
                "verdict": "REFUTED — the claim is false at this point",
            }
    return {
        "claim": claim,
        "refuted": False,
        "counterexample": None,
        "verdict": f"survived {samples} samples on [{low}, {high}] — evidence, not proof",
    }


@tool
def limiting_case_check(expression: str, variable: str, approaching: str, expected: str) -> dict[str, Any]:
    """Check that an expression behaves correctly in a limiting case.

    The standard sanity check on a derived formula: does it collapse to the
    simple answer when a parameter vanishes, or grow as it should at infinity.

    Args:
        expression: The general result, e.g. "m*v**2/2 * 1/sqrt(1 - v**2/c**2)".
        variable: The parameter being taken to a limit, e.g. "v".
        approaching: Target value; use "oo" for infinity.
        expected: What the limit should be, e.g. "0".
    """
    symbol = sp.Symbol(variable)
    target = _parse(approaching)
    try:
        actual = sp.limit(_parse(expression), symbol, target)
    except (NotImplementedError, ValueError, TypeError) as error:
        raise ToolError(f"could not take the limit: {error}") from error

    want = _parse(expected)
    matches = bool(sp.simplify(actual - want) == 0)
    return {
        "expression": expression,
        "limit": f"{variable} -> {approaching}",
        "actual": str(actual),
        "expected": expected,
        "matches": matches,
        "verdict": "limiting case correct" if matches else "LIMITING CASE WRONG — the general result is suspect",
    }


@tool
def plausibility_check(
    expression: str,
    substitutions: dict,
    expect_sign: str = "any",
    minimum: float | None = None,
    maximum: float | None = None,
) -> dict[str, Any]:
    """Check a physical result for sign, magnitude, and finiteness.

    Catches results that are dimensionally fine and algebraically derived and
    still cannot be true: a negative kinetic energy, a speed above c, an
    infinite force.

    Args:
        expression: The result to evaluate.
        substitutions: Value per symbol, e.g. {"m": 2, "v": 3}.
        expect_sign: "positive", "negative", "non-negative", or "any".
        minimum: Optional lower bound the value must not fall below.
        maximum: Optional upper bound the value must not exceed.
    """
    expression_obj = _parse(expression)
    point = {sp.Symbol(k): v for k, v in substitutions.items()}
    missing = sorted(str(s) for s in expression_obj.free_symbols if s not in point)
    if missing:
        raise ToolError(f"no value given for {missing}")

    try:
        value = float(sp.N(expression_obj.subs(point)))
    except (TypeError, ValueError) as error:
        raise ToolError(f"could not evaluate: {error}") from error

    problems = []
    if not math.isfinite(value):
        problems.append("not finite")
    if expect_sign == "positive" and value <= 0:
        problems.append(f"expected positive, got {value:g}")
    if expect_sign == "negative" and value >= 0:
        problems.append(f"expected negative, got {value:g}")
    if expect_sign == "non-negative" and value < 0:
        problems.append(f"expected non-negative, got {value:g}")
    if minimum is not None and value < minimum:
        problems.append(f"below the stated minimum {minimum:g}")
    if maximum is not None and value > maximum:
        problems.append(f"above the stated maximum {maximum:g}")

    return {
        "expression": expression,
        "value": value,
        "plausible": not problems,
        "problems": problems,
        "verdict": "plausible" if not problems else "IMPLAUSIBLE — " + "; ".join(problems),
    }


@tool
def assumption_check(assumptions: list[str], substitutions: dict) -> dict[str, Any]:
    """Test whether the conditions a derivation depends on actually hold.

    A result is only valid where its assumptions are. This is what lets an
    interactive parameter know where the theorem stops being true.

    Args:
        assumptions: Conditions as inequalities or equations, e.g.
            ["eta > 0", "eta < 2/L", "x != 0"].
        substitutions: Value per symbol, e.g. {"eta": 0.5, "L": 2}.
    """
    point = {sp.Symbol(k): v for k, v in substitutions.items()}
    results = []
    for assumption in assumptions:
        try:
            if "!=" in assumption:
                left, _, right = assumption.partition("!=")
                holds = bool(sp.N((_parse(left) - _parse(right)).subs(point)) != 0)
            else:
                left, right, relation = _sides(assumption)
                holds = _holds(relation, float(sp.N((left - right).subs(point))))
        except (ToolError, TypeError, ValueError) as error:
            results.append({"assumption": assumption, "holds": None, "note": str(error)[:120]})
            continue
        results.append({"assumption": assumption, "holds": holds})

    violated = [r["assumption"] for r in results if r["holds"] is False]
    return {
        "checked": results,
        "all_hold": not violated,
        "violated": violated,
        "verdict": "all assumptions hold" if not violated else f"OUTSIDE VALIDITY — violated: {', '.join(violated)}",
    }


@tool
def induction_check(claim: str, variable: str = "n", base: int = 1, steps: int = 12) -> dict[str, Any]:
    """Check a claim over the integers: base case, then successive values.

    Not a proof of the inductive step, and says so. It is the check that stops a
    false summation formula from being animated as though it were established.

    Args:
        claim: e.g. "Sum(k, (k, 1, n)) = n*(n+1)/2".
        variable: The induction variable.
        base: First value to test.
        steps: How many consecutive values to test.
    """
    left, right, relation = _sides(claim)
    symbol = sp.Symbol(variable)
    failures = []
    for value in range(base, base + max(1, steps)):
        try:
            difference = sp.simplify(sp.N((left - right).subs(symbol, value).doit()))
            ok = _holds(relation, float(difference))
        except (TypeError, ValueError) as error:
            failures.append({"n": value, "note": str(error)[:100]})
            continue
        if not ok:
            failures.append({"n": value, "difference": str(difference)})

    return {
        "claim": claim,
        "base": base,
        "tested": steps,
        "holds_for_all_tested": not failures,
        "failures": failures[:5],
        "verdict": (
            f"holds for {variable}={base}..{base + steps - 1}; the inductive step still needs a proof"
            if not failures
            else f"FAILS at {variable}={failures[0]['n']}"
        ),
    }


@tool
def symmetry_check(expression: str, substitution: dict, expect: str = "invariant") -> dict[str, Any]:
    """Check that an expression respects a symmetry it should.

    Even and odd functions, exchange symmetry between two bodies, invariance
    under a shift. A result that breaks a symmetry the problem has is wrong.

    Args:
        expression: e.g. "x**2 + y**2".
        substitution: The transformation, e.g. {"x": "-x"} or {"a": "b", "b": "a"}.
        expect: "invariant" (unchanged) or "antisymmetric" (negated).
    """
    original = _parse(expression)
    mapping = {sp.Symbol(k): _parse(v) for k, v in substitution.items()}
    transformed = original.subs(mapping, simultaneous=True)

    difference = sp.simplify(transformed - original)
    total = sp.simplify(transformed + original)
    invariant, antisymmetric = difference == 0, total == 0

    satisfied = invariant if expect == "invariant" else antisymmetric
    return {
        "expression": expression,
        "transformation": substitution,
        "transformed": str(transformed),
        "invariant": bool(invariant),
        "antisymmetric": bool(antisymmetric),
        "expected": expect,
        "satisfied": bool(satisfied),
        "verdict": f"symmetry {'holds' if satisfied else 'BROKEN'} under {substitution}",
    }
