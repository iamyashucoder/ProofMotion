"""Number theory, combinatorics, logic, and graphs.

Four subjects that share a property: the answers are exact integers or exact
structures, so an agent guessing at them is simply wrong, and a tool is simply
right.
"""

from __future__ import annotations

from typing import Any, Literal

import sympy as sp

from proofmotion.runtime.registry import ToolError, tool


@tool
def number_theory(
    operation: Literal[
        "gcd", "lcm", "factorize", "is_prime", "next_prime", "totient",
        "mod_inverse", "crt", "divisors", "mod_power",
    ],
    values: list,
    modulus: int = 0,
) -> dict[str, Any]:
    """Exact integer arithmetic: gcd, factorisation, primality, modular inverse, CRT.

    Args:
        operation: What to compute.
        values: Integers the operation acts on. For crt, pass the remainders and
            give the moduli in `modulus` as a comma-joined string is not
            supported — instead pass pairs, e.g. [[2,3],[3,5],[2,7]].
        modulus: Modulus for mod_inverse and mod_power.
    """
    try:
        if operation == "crt":
            pairs = [(int(r), int(m)) for r, m in values]
            residues, moduli = zip(*pairs, strict=True)
            solution = sp.ntheory.modular.crt(moduli, residues)
            if solution is None:
                raise ToolError("no solution: the moduli are not pairwise coprime")
            return {"operation": operation, "result": int(solution[0]), "modulus": int(solution[1])}

        numbers = [int(v) for v in values]
        if operation == "gcd":
            result: Any = sp.gcd(numbers) if len(numbers) > 1 else numbers[0]
        elif operation == "lcm":
            result = sp.lcm(numbers) if len(numbers) > 1 else numbers[0]
        elif operation == "factorize":
            result = {str(k): v for k, v in sp.factorint(numbers[0]).items()}
        elif operation == "is_prime":
            result = bool(sp.isprime(numbers[0]))
        elif operation == "next_prime":
            result = int(sp.nextprime(numbers[0]))
        elif operation == "totient":
            result = int(sp.totient(numbers[0]))
        elif operation == "divisors":
            result = [int(d) for d in sp.divisors(numbers[0])]
        elif operation == "mod_inverse":
            if not modulus:
                raise ToolError("mod_inverse needs a modulus")
            result = int(sp.mod_inverse(numbers[0], modulus))
        else:
            if not modulus:
                raise ToolError("mod_power needs a modulus")
            result = int(pow(numbers[0], numbers[1], modulus))
    except ToolError:
        raise
    except (ValueError, TypeError, NotImplementedError, ZeroDivisionError) as error:
        raise ToolError(f"{operation} failed: {error}") from error

    return {"operation": operation, "values": values, "result": result}


@tool
def combinatorics(
    operation: Literal["permutations", "combinations", "binomial", "factorial", "catalan", "partitions", "stirling"],
    n: int,
    k: int = 0,
) -> dict[str, Any]:
    """Exact counting: nPr, nCr, binomial coefficients, Catalan and Stirling numbers.

    Args:
        operation: Which count to compute.
        n: The size of the set.
        k: The size of the selection, where the operation needs one.
    """
    if n < 0 or k < 0:
        raise ToolError("n and k must be non-negative")
    try:
        if operation == "permutations":
            result = int(sp.factorial(n) / sp.factorial(n - k)) if k <= n else 0
        elif operation in {"combinations", "binomial"}:
            result = int(sp.binomial(n, k))
        elif operation == "factorial":
            result = int(sp.factorial(n))
        elif operation == "catalan":
            result = int(sp.catalan(n))
        elif operation == "partitions":
            result = int(sp.npartitions(n))
        else:
            result = int(sp.functions.combinatorial.numbers.stirling(n, k))
    except (ValueError, TypeError, OverflowError) as error:
        raise ToolError(f"{operation} failed: {error}") from error
    return {"operation": operation, "n": n, "k": k, "result": result}


@tool
def logic_table(expression: str, variables: list | None = None) -> dict[str, Any]:
    """Build a truth table and report tautology or contradiction.

    Args:
        expression: Boolean expression using & | ~ >> for and, or, not, implies.
            Parenthesise implications: Python binds >> tighter than &, so
            "(p >> q) & p >> q" reads as "(p>>q) & (p>>q)", not as modus ponens.
            Write modus ponens as "((p >> q) & p) >> q".
        variables: Variable names, defaulting to the symbols found.
    """
    from sympy.logic.boolalg import truth_table
    from sympy.parsing.sympy_parser import parse_expr

    try:
        formula = parse_expr(expression, evaluate=False)
    except (SyntaxError, TypeError, ValueError) as error:
        raise ToolError(f"could not parse {expression!r}: {error}") from error

    symbols = [sp.Symbol(v) for v in variables] if variables else sorted(formula.free_symbols, key=str)
    if not symbols:
        raise ToolError("no variables found in the expression")
    if len(symbols) > 12:
        raise ToolError(f"{len(symbols)} variables would need {2 ** len(symbols)} rows; keep it under 12")

    rows = [{"assignment": list(inputs), "value": bool(output)} for inputs, output in truth_table(formula, symbols)]
    outputs = [r["value"] for r in rows]
    return {
        "expression": expression,
        "variables": [str(s) for s in symbols],
        "rows": rows,
        "tautology": all(outputs),
        "contradiction": not any(outputs),
        "satisfiable": any(outputs),
    }


@tool
def graph_algorithm(
    edges: list,
    operation: Literal[
        "shortest_path", "connected_components", "is_bipartite", "cycles",
        "minimum_spanning_tree", "topological_sort", "degree", "diameter",
    ],
    source: str = "",
    target: str = "",
    directed: bool = False,
) -> dict[str, Any]:
    """Graph computations: paths, components, spanning trees, cycles.

    Args:
        edges: Edge list, e.g. [["a","b"], ["b","c"]] or with weights
            [["a","b",3], ["b","c",1]].
        operation: What to compute.
        source: Start node, where the operation needs one.
        target: End node, where the operation needs one.
        directed: Treat edges as directed.
    """
    import networkx as nx

    graph = nx.DiGraph() if directed else nx.Graph()
    for edge in edges:
        if len(edge) == 3:
            graph.add_edge(str(edge[0]), str(edge[1]), weight=float(edge[2]))
        elif len(edge) == 2:
            graph.add_edge(str(edge[0]), str(edge[1]))
        else:
            raise ToolError(f"edge {edge!r} must have two nodes and an optional weight")

    weighted = any(len(e) == 3 for e in edges)
    try:
        if operation == "shortest_path":
            if not source or not target:
                raise ToolError("shortest_path needs source and target")
            path = nx.shortest_path(graph, source, target, weight="weight" if weighted else None)
            length = nx.shortest_path_length(graph, source, target, weight="weight" if weighted else None)
            result: Any = {"path": path, "length": float(length)}
        elif operation == "connected_components":
            finder = nx.weakly_connected_components if directed else nx.connected_components
            result = [sorted(c) for c in finder(graph)]
        elif operation == "is_bipartite":
            result = bool(nx.is_bipartite(graph))
        elif operation == "cycles":
            result = [list(c) for c in nx.simple_cycles(graph)][:20]
        elif operation == "minimum_spanning_tree":
            if directed:
                raise ToolError("minimum_spanning_tree needs an undirected graph")
            tree = nx.minimum_spanning_tree(graph)
            result = {"edges": sorted(tuple(sorted(e)) for e in tree.edges()),
                      "weight": float(sum(d.get("weight", 1) for _, _, d in tree.edges(data=True)))}
        elif operation == "topological_sort":
            if not directed:
                raise ToolError("topological_sort needs a directed graph")
            result = list(nx.topological_sort(graph))
        elif operation == "degree":
            result = {n: int(d) for n, d in graph.degree()}
        else:
            result = int(nx.diameter(graph))
    except ToolError:
        raise
    except (nx.NetworkXException, ValueError, KeyError) as error:
        raise ToolError(f"{operation} failed: {error}") from error

    return {"operation": operation, "nodes": graph.number_of_nodes(), "edges": graph.number_of_edges(), "result": result}
