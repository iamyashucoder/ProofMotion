"""Algebra and linear algebra.

Thin, tested wrappers over sympy. The point is not that sympy can do this — it
is that the agent gets a checked answer with a schema instead of writing the
manipulation itself and hoping.
"""

from __future__ import annotations

from typing import Any, Literal

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


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


def _matrix(rows: list[list]) -> sp.Matrix:
    if not rows or not all(isinstance(r, list) for r in rows):
        raise ToolError("expected a list of rows, e.g. [[1, 2], [3, 4]]")
    width = len(rows[0])
    if any(len(r) != width for r in rows):
        raise ToolError("every row must have the same length")
    try:
        return sp.Matrix([[_parse(str(v)) if isinstance(v, str) else sp.nsimplify(v) for v in row] for row in rows])
    except (TypeError, ValueError) as error:
        raise ToolError(f"could not build a matrix: {error}") from error


@tool
def symbolic_algebra(
    expression: str,
    operation: Literal["factor", "expand", "apart", "together", "cancel", "trig_simplify", "rationalize"],
    variable: str = "x",
) -> dict[str, Any]:
    """Rewrite an expression: factor, expand, partial fractions, and friends.

    Use this rather than performing the manipulation yourself — an expansion done
    in your head is a claim; this one is computed.

    Args:
        expression: e.g. "x**2 - 1" or "(x**2+1)/(x**2-1)".
        operation: Which rewrite to apply.
        variable: The variable for operations that need one, such as apart.
    """
    expr, symbol = _parse(expression), sp.Symbol(variable)
    operations = {
        "factor": lambda: sp.factor(expr),
        "expand": lambda: sp.expand(expr),
        "apart": lambda: sp.apart(expr, symbol),
        "together": lambda: sp.together(expr),
        "cancel": lambda: sp.cancel(expr),
        "trig_simplify": lambda: sp.trigsimp(expr),
        "rationalize": lambda: sp.radsimp(expr),
    }
    try:
        result = operations[operation]()
    except (sp.PolynomialError, NotImplementedError, ValueError, ZeroDivisionError) as error:
        raise ToolError(f"{operation} failed on {expression!r}: {error}") from error
    return {
        "input": expression,
        "operation": operation,
        "result": str(result),
        "latex": sp.latex(result),
        "unchanged": bool(sp.simplify(result - expr) == 0 and str(result) == str(expr)),
    }


@tool
def symbolic_matrix(
    rows: list,
    operation: Literal[
        "determinant", "inverse", "rank", "transpose", "eigenvalues", "eigenvectors",
        "rref", "nullspace", "columnspace", "trace", "characteristic_polynomial", "diagonalize",
    ],
) -> dict[str, Any]:
    """Matrix operations, exactly, over a matrix given as rows.

    Covers the linear-algebra topics as computation: determinants, rank,
    eigen-decomposition, row reduction, null space, diagonalisation.

    Args:
        rows: The matrix, e.g. [[1, 2], [3, 4]]. Entries may be numbers or
            expressions such as "a" or "x+1".
        operation: What to compute.
    """
    matrix = _matrix(rows)
    square = matrix.rows == matrix.cols
    needs_square = {
        "determinant", "inverse", "eigenvalues", "eigenvectors", "trace",
        "characteristic_polynomial", "diagonalize",
    }
    if operation in needs_square and not square:
        raise ToolError(f"{operation} needs a square matrix; got {matrix.rows}x{matrix.cols}")

    try:
        if operation == "determinant":
            value = matrix.det()
        elif operation == "inverse":
            if matrix.det() == 0:
                raise ToolError("the matrix is singular, so it has no inverse")
            value = matrix.inv()
        elif operation == "rank":
            value = matrix.rank()
        elif operation == "transpose":
            value = matrix.T
        elif operation == "eigenvalues":
            value = {str(k): v for k, v in matrix.eigenvals().items()}
        elif operation == "eigenvectors":
            value = [
                {"eigenvalue": str(val), "multiplicity": mult, "vectors": [str(v.T.tolist()) for v in vecs]}
                for val, mult, vecs in matrix.eigenvects()
            ]
        elif operation == "rref":
            reduced, pivots = matrix.rref()
            value = {"matrix": str(reduced.tolist()), "pivot_columns": list(pivots)}
        elif operation == "nullspace":
            value = [str(v.T.tolist()) for v in matrix.nullspace()]
        elif operation == "columnspace":
            value = [str(v.T.tolist()) for v in matrix.columnspace()]
        elif operation == "trace":
            value = matrix.trace()
        elif operation == "characteristic_polynomial":
            value = matrix.charpoly().as_expr()
        else:
            P, D = matrix.diagonalize()
            value = {"P": str(P.tolist()), "D": str(D.tolist())}
    except ToolError:
        raise
    except (sp.MatrixError, NotImplementedError, ValueError, TypeError) as error:
        raise ToolError(f"{operation} failed: {error}") from error

    return {
        "shape": [matrix.rows, matrix.cols],
        "operation": operation,
        "result": str(value) if not isinstance(value, (dict, list)) else value,
        "latex": sp.latex(value) if isinstance(value, (sp.Matrix, sp.Expr)) else None,
    }


@tool
def symbolic_vector_calculus(
    field: list,
    operation: Literal["gradient", "divergence", "curl", "jacobian", "hessian", "laplacian"],
    variables: list | None = None,
) -> dict[str, Any]:
    """Gradient, divergence, curl, Jacobian, Hessian, Laplacian.

    Args:
        field: For gradient/hessian/laplacian a single scalar expression as a
            one-element list, e.g. ["x**2 + y**2"]. For divergence/curl the
            components, e.g. ["x", "y", "z"]. For jacobian the component list.
        operation: Which operator to apply.
        variables: Variable names, defaulting to ["x", "y", "z"] truncated to fit.
    """
    if not field:
        raise ToolError("field must contain at least one expression")
    names = variables or ["x", "y", "z"][: max(len(field), 2)]
    symbols = [sp.Symbol(n) for n in names]
    components = [_parse(str(f)) for f in field]

    try:
        if operation == "gradient":
            result = [sp.diff(components[0], s) for s in symbols]
        elif operation == "divergence":
            if len(components) != len(symbols):
                raise ToolError("divergence needs one component per variable")
            result = sum(sp.diff(c, s) for c, s in zip(components, symbols, strict=True))
        elif operation == "curl":
            if len(components) != 3 or len(symbols) != 3:
                raise ToolError("curl needs three components and three variables")
            fx, fy, fz = components
            x, y, z = symbols
            result = [
                sp.diff(fz, y) - sp.diff(fy, z),
                sp.diff(fx, z) - sp.diff(fz, x),
                sp.diff(fy, x) - sp.diff(fx, y),
            ]
        elif operation == "jacobian":
            result = sp.Matrix(components).jacobian(symbols)
        elif operation == "hessian":
            result = sp.hessian(components[0], symbols)
        else:
            result = sum(sp.diff(components[0], s, 2) for s in symbols)
    except ToolError:
        raise
    except (TypeError, ValueError, NotImplementedError) as error:
        raise ToolError(f"{operation} failed: {error}") from error

    rendered = [str(r) for r in result] if isinstance(result, list) else str(result)
    return {
        "operation": operation,
        "variables": names,
        "result": rendered,
        "latex": sp.latex(result if not isinstance(result, list) else sp.Matrix(result)),
    }
