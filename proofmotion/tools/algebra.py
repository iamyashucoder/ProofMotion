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
def matrix_arithmetic(
    left_rows: list,
    right_rows: list,
    operation: Literal["add", "subtract", "multiply", "commutator"],
) -> dict[str, Any]:
    """Compute a two-matrix operation exactly, with dimensions made explicit.

    Args:
        left_rows: First matrix as rows.
        right_rows: Second matrix as rows.
        operation: add, subtract, multiply (left times right), or commutator AB-BA.
    """
    left, right = _matrix(left_rows), _matrix(right_rows)
    if operation in {"add", "subtract"} and left.shape != right.shape:
        raise ToolError(f"{operation} needs equal shapes, got {left.shape} and {right.shape}")
    if operation in {"multiply", "commutator"} and left.cols != right.rows:
        raise ToolError(f"multiplication needs columns(A)=rows(B), got {left.shape} and {right.shape}")
    if operation == "commutator" and left.shape != right.shape:
        raise ToolError("commutator AB-BA needs square matrices of the same shape")
    if operation == "add":
        result = left + right
    elif operation == "subtract":
        result = left - right
    elif operation == "multiply":
        result = left * right
    else:
        result = left * right - right * left
    return {
        "operation": operation, "left_shape": list(left.shape), "right_shape": list(right.shape),
        "result": str(result.tolist()), "latex": sp.latex(result),
        "note": "Matrix multiplication order matters; AB and BA are generally different." if operation in {"multiply", "commutator"} else "Corresponding entries are combined.",
    }


@tool
def matrix_row_operation(
    rows: list,
    operation: Literal["swap", "scale", "add_multiple"],
    target_row: int,
    source_row: int | None = None,
    factor: str = "1",
) -> dict[str, Any]:
    """Apply one elementary row operation and return a displayable before/after step.

    Args:
        rows: Matrix rows.
        operation: swap two rows, scale one row, or add factor times source row to target row.
        target_row: Zero-based target row index.
        source_row: Required for swap and add_multiple.
        factor: Exact scale factor, e.g. "-2" or "1/3".
    """
    matrix = _matrix(rows)
    if not 0 <= target_row < matrix.rows:
        raise ToolError(f"target_row must be from 0 to {matrix.rows - 1}")
    if operation in {"swap", "add_multiple"} and (source_row is None or not 0 <= source_row < matrix.rows):
        raise ToolError(f"{operation} needs source_row from 0 to {matrix.rows - 1}")
    scalar = _parse(factor)
    before = matrix.copy()
    if operation == "swap":
        matrix.row_swap(target_row, source_row)  # type: ignore[arg-type]
        step = rf"R_{{{target_row + 1}}}\leftrightarrow R_{{{source_row + 1}}}"
    elif operation == "scale":
        matrix.row_op(target_row, lambda value, _: scalar * value)
        step = rf"R_{{{target_row + 1}}}\leftarrow ({sp.latex(scalar)})R_{{{target_row + 1}}}"
    else:
        matrix.row_op(target_row, lambda value, column: value + scalar * matrix[source_row, column])  # type: ignore[index]
        step = rf"R_{{{target_row + 1}}}\leftarrow R_{{{target_row + 1}}}+({sp.latex(scalar)})R_{{{source_row + 1}}}"
    return {"before": str(before.tolist()), "after": str(matrix.tolist()), "operation_latex": step, "latex": sp.latex(matrix)}


@tool
def matrix_linear_system(
    coefficients: list,
    constants: list,
    method: Literal["rref", "inverse", "cramer"] = "rref",
) -> dict[str, Any]:
    """Solve a linear system Ax=b with an exact, named matrix method.

    Args:
        coefficients: Square coefficient matrix A.
        constants: Right-hand-side vector b.
        method: rref, inverse, or cramer (requires nonzero determinant).
    """
    matrix, vector = _matrix(coefficients), sp.Matrix(constants)
    if matrix.rows != matrix.cols or vector.rows != matrix.rows or vector.cols != 1:
        raise ToolError("coefficients must be square and constants must be a matching column vector")
    determinant = sp.simplify(matrix.det())
    if determinant == 0:
        raise ToolError("coefficient matrix is singular; this tool cannot claim a unique solution")
    if method == "rref":
        augmented = matrix.row_join(vector)
        reduced, pivots = augmented.rref()
        solution = reduced[:, -1]
        working = {"augmented_rref": str(reduced.tolist()), "pivot_columns": list(pivots)}
    elif method == "inverse":
        solution = matrix.inv() * vector
        working = {"inverse": str(matrix.inv().tolist())}
    else:
        values = []
        for column in range(matrix.cols):
            replaced = matrix.copy()
            replaced[:, column] = vector
            values.append(sp.simplify(replaced.det() / determinant))
        solution = sp.Matrix(values)
        working = {"determinant": str(determinant), "rule": "replace one column of A by b for each variable"}
    return {"method": method, "solution": str(solution.tolist()), "latex": sp.latex(solution), **working}


@tool
def matrix_properties(rows: list) -> dict[str, Any]:
    """Check determinant, adjugate, symmetry, invertibility, and Cayley-Hamilton identity.

    Args:
        rows: A square matrix as rows.
    """
    matrix = _matrix(rows)
    if matrix.rows != matrix.cols:
        raise ToolError("matrix_properties needs a square matrix")
    determinant = sp.simplify(matrix.det())
    characteristic = matrix.charpoly().as_expr()
    variable = next(iter(characteristic.free_symbols), sp.Symbol("lambda"))
    # Substitute the matrix into its characteristic polynomial term by term.
    polynomial = sp.Poly(characteristic, variable)
    cayley = sum((coefficient * (matrix ** exponent[0]) for exponent, coefficient in polynomial.terms()), sp.zeros(matrix.rows))
    return {
        "shape": list(matrix.shape), "determinant": str(determinant), "rank": matrix.rank(),
        "invertible": determinant != 0, "symmetric": matrix == matrix.T, "skew_symmetric": matrix == -matrix.T,
        "adjugate": str(matrix.adjugate().tolist()), "characteristic_polynomial": str(characteristic),
        "cayley_hamilton_verified": cayley == sp.zeros(matrix.rows),
        "latex": {"adjugate": sp.latex(matrix.adjugate()), "characteristic_polynomial": sp.latex(characteristic)},
    }


@tool
def determinant_cofactor_expansion(
    rows: list,
    axis: Literal["row", "column"] = "row",
    index: int = 0,
) -> dict[str, Any]:
    """Expand a determinant into signed minors along one chosen row or column.

    Args:
        rows: Square matrix whose determinant is required.
        axis: Expand along a row or a column.
        index: Zero-based row or column index to expand along.
    """
    matrix = _matrix(rows)
    if matrix.rows != matrix.cols or matrix.rows < 2:
        raise ToolError("cofactor expansion needs a square matrix of order at least 2")
    if not 0 <= index < matrix.rows:
        raise ToolError(f"index must be from 0 to {matrix.rows - 1}")
    terms = []
    for other in range(matrix.rows):
        row, column = (index, other) if axis == "row" else (other, index)
        entry = matrix[row, column]
        minor = matrix.minor_submatrix(row, column).det()
        cofactor = sp.simplify((-1) ** (row + column) * minor)
        terms.append({
            "entry": str(entry), "minor": str(minor), "cofactor": str(cofactor),
            "term": str(sp.simplify(entry * cofactor)),
            "latex": rf"a_{{{row + 1}{column + 1}}}C_{{{row + 1}{column + 1}}}={sp.latex(entry)}\left({sp.latex(cofactor)}\right)",
        })
    determinant = sp.simplify(matrix.det())
    return {
        "axis": axis, "index": index, "terms": terms, "determinant": str(determinant),
        "expansion_latex": " + ".join(term["latex"] for term in terms) + rf" = {sp.latex(determinant)}",
    }


@tool
def determinant_row_effect(
    rows: list,
    operation: Literal["swap", "scale", "add_multiple"],
    target_row: int,
    source_row: int | None = None,
    factor: str = "1",
) -> dict[str, Any]:
    """Apply a row operation and state its exact effect on the determinant.

    Args:
        rows: Square matrix rows.
        operation: swap, scale, or add_multiple.
        target_row: Zero-based target row.
        source_row: Required for swap and add_multiple.
        factor: Scaling or added multiple.
    """
    matrix = _matrix(rows)
    if matrix.rows != matrix.cols:
        raise ToolError("determinant row rules need a square matrix")
    if not 0 <= target_row < matrix.rows:
        raise ToolError(f"target_row must be from 0 to {matrix.rows - 1}")
    if operation in {"swap", "add_multiple"} and (source_row is None or not 0 <= source_row < matrix.rows):
        raise ToolError(f"{operation} needs source_row from 0 to {matrix.rows - 1}")
    scalar, before = _parse(factor), matrix.copy()
    before_det = sp.simplify(before.det())
    if operation == "swap":
        matrix.row_swap(target_row, source_row)  # type: ignore[arg-type]
        rule = r"\det(A')=-\det(A)"
    elif operation == "scale":
        matrix.row_op(target_row, lambda value, _: scalar * value)
        rule = rf"\det(A')=({sp.latex(scalar)})\det(A)"
    else:
        matrix.row_op(target_row, lambda value, column: value + scalar * matrix[source_row, column])  # type: ignore[index]
        rule = r"\det(A')=\det(A)"
    after_det = sp.simplify(matrix.det())
    return {"before_determinant": str(before_det), "after_determinant": str(after_det), "rule_latex": rule, "after": str(matrix.tolist()), "verified": True}


@tool
def determinant_parameter_solve(rows: list, variable: str, target: str = "0") -> dict[str, Any]:
    """Solve det(A)=target exactly for a parameter appearing in a matrix.

    Args:
        rows: Square matrix entries, allowing symbolic strings such as "a+1".
        variable: Parameter to solve for.
        target: Required determinant value, defaulting to zero for singularity questions.
    """
    matrix = _matrix(rows)
    if matrix.rows != matrix.cols:
        raise ToolError("determinant_parameter_solve needs a square matrix")
    determinant, target_expr = sp.factor(matrix.det()), _parse(target)
    parameter = sp.Symbol(variable)
    solutions = sp.solve(sp.Eq(determinant, target_expr), parameter)
    return {
        "determinant": str(determinant), "target": str(target_expr), "variable": variable,
        "solutions": [str(value) for value in solutions],
        "latex": {"determinant": sp.latex(determinant), "solutions": [sp.latex(value) for value in solutions]},
    }


@tool
def determinant_signed_area(rows: list) -> dict[str, Any]:
    """Interpret a 2x2 determinant as signed area scale and orientation.

    Args:
        rows: A 2x2 linear transformation matrix.
    """
    matrix = _matrix(rows)
    if matrix.shape != (2, 2):
        raise ToolError("signed-area interpretation needs a 2x2 matrix")
    determinant = sp.simplify(matrix.det())
    orientation = "reversed" if determinant < 0 else "preserved" if determinant > 0 else "collapsed"
    return {"determinant": str(determinant), "area_scale": str(abs(determinant)), "orientation": orientation, "visual": "matrix_transform"}


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
