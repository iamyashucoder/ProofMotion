"""Ground truth about the Manim API, queried instead of memorised.

This module exists to delete prompts.py. Manim exposes ~1200 unique methods and
~2800 valid (method, parameter) pairs; a prompt listing 47 remembered rules
covers a rounding error of that, and every rule was added only after someone hit
the bug. An agent that can look up a signature does not need to be told.
"""

from __future__ import annotations

import ast
import functools
import inspect
from difflib import get_close_matches
from typing import Any

from proofmotion.runtime.registry import ToolError, tool


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    """Build a searchable index of the real Manim namespace. Cached; import is slow."""
    import manim

    classes: dict[str, type] = {}
    methods: dict[str, list[str]] = {}
    for name in dir(manim):
        if name.startswith("_"):
            continue
        obj = getattr(manim, name)
        if not inspect.isclass(obj):
            continue
        classes[name] = obj
        # isroutine, not isfunction: classmethods and staticmethods are real API
        # too, and missing them makes the validator reject valid code.
        for member, _ in inspect.getmembers(obj, inspect.isroutine):
            if not member.startswith("_"):
                methods.setdefault(member, []).append(name)
    return {"module": manim, "classes": classes, "methods": methods}


def _params(fn: Any) -> tuple[list[str], bool]:
    """Accepted parameter names, and whether the callable also takes **kwargs."""
    try:
        signature = inspect.signature(fn)
    except (ValueError, TypeError):
        return [], True
    names, permissive = [], False
    for name, param in signature.parameters.items():
        if param.kind is param.VAR_KEYWORD:
            permissive = True
        elif param.kind is not param.VAR_POSITIONAL and name != "self":
            names.append(name)
    return names, permissive


def _accepted_by_class(cls: type) -> tuple[set[str], bool]:
    """Constructor parameters across the MRO.

    Manim constructors chain **kwargs up to Mobject, so the honest allowlist is
    the union along the MRO rather than the leaf signature alone.
    """
    accepted: set[str] = set()
    permissive = False
    for base in cls.__mro__:
        init = base.__dict__.get("__init__")
        if init is None:
            continue
        names, takes_kwargs = _params(init)
        accepted.update(names)
        permissive = permissive or takes_kwargs
    return accepted, permissive


def _resolve(qualname: str) -> Any:
    """Resolve 'Axes', 'Axes.plot', or a full dotted path to a live object."""
    index = _index()
    parts = qualname.replace("manim.", "").split(".")
    # Tolerate full module paths by taking the last class-looking component onward.
    for start in range(len(parts)):
        head = parts[start]
        if head in index["classes"]:
            obj: Any = index["classes"][head]
            for attr in parts[start + 1 :]:
                obj = getattr(obj, attr, None)
                if obj is None:
                    raise ToolError(f"{head} has no member {attr!r}. Use manim_members({head!r}) to list them.")
            return obj
    if hasattr(index["module"], parts[-1]):
        return getattr(index["module"], parts[-1])
    close = get_close_matches(parts[-1], list(index["classes"]), n=5)
    raise ToolError(f"Unknown Manim name {qualname!r}." + (f" Did you mean: {', '.join(close)}?" if close else ""))


@tool
def manim_search(query: str, limit: int = 20) -> dict[str, Any]:
    """Find Manim classes and methods whose names match a query.

    Use this before writing code when unsure what exists. Never guess a name.

    Args:
        query: Substring or approximate name, e.g. "secant" or "riemann".
        limit: Maximum results per category.
    """
    index = _index()
    q = query.lower()
    classes = [n for n in index["classes"] if q in n.lower()]
    methods = [f"{owner}.{m}" for m, owners in index["methods"].items() if q in m.lower() for owner in owners[:3]]
    if not classes and not methods:
        classes = get_close_matches(query, list(index["classes"]), n=limit, cutoff=0.6)
        methods = [f"{o[0]}.{m}" for m, o in index["methods"].items() if get_close_matches(query, [m], cutoff=0.7)]
    return {"query": query, "classes": sorted(classes)[:limit], "methods": sorted(methods)[:limit]}


@tool
def manim_signature(qualname: str) -> dict[str, Any]:
    """Return the real signature of a Manim class or method, with defaults and docs.

    Authoritative: read from the installed Manim, not from memory.

    Args:
        qualname: e.g. "Axes.get_secant_slope_group", "MathTex", "Axes.plot".
    """
    obj = _resolve(qualname)
    target = obj.__init__ if inspect.isclass(obj) else obj
    try:
        signature = inspect.signature(target)
    except (ValueError, TypeError) as error:
        raise ToolError(f"{qualname}: signature unavailable ({error})") from error

    parameters = []
    for name, param in signature.parameters.items():
        if name == "self":
            continue
        parameters.append(
            {
                "name": name,
                "kind": param.kind.name.lower(),
                "default": None if param.default is inspect.Parameter.empty else repr(param.default),
                "required": param.default is inspect.Parameter.empty and param.kind is not param.VAR_KEYWORD,
                "annotation": None if param.annotation is inspect.Parameter.empty else str(param.annotation),
            }
        )
    doc = inspect.getdoc(target) or inspect.getdoc(obj) or ""
    return {
        "qualname": qualname,
        "is_class": inspect.isclass(obj),
        "parameters": parameters,
        "doc": doc[:1200],
    }


@tool
def manim_members(class_name: str, filter: str = "") -> dict[str, Any]:
    """List the public methods of a Manim class, including inherited ones.

    Args:
        class_name: e.g. "Axes", "VMobject", "Scene".
        filter: Optional substring to narrow the list.
    """
    obj = _resolve(class_name)
    if not inspect.isclass(obj):
        raise ToolError(f"{class_name} is not a class.")
    members = [n for n, _ in inspect.getmembers(obj, inspect.isfunction) if not n.startswith("_")]
    if filter:
        members = [m for m in members if filter.lower() in m.lower()]
    return {"class": class_name, "mro": [c.__name__ for c in obj.__mro__[:6]], "methods": sorted(members)}


@tool
def manim_validate_code(code: str) -> dict[str, Any]:
    """Check Manim code against the real API before rendering it.

    Catches hallucinated keyword arguments and unknown class names in
    milliseconds, instead of discovering them via a 90-second render failure.
    Reports the valid parameters alongside each problem so the fix is a lookup
    rather than another guess.

    Args:
        code: A complete Manim scene source file.
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as error:
        return {"valid": False, "problems": [{"line": error.lineno, "problem": f"SyntaxError: {error.msg}"}]}

    index = _index()
    problems: list[dict[str, Any]] = []

    # `from manim import *` does not bind the name `manim`, so `manim.Circle(...)`
    # raises NameError at render time while looking perfectly reasonable.
    imports_module = any(
        isinstance(n, ast.Import) and any(a.name.split(".")[0] == "manim" for a in n.names) for n in ast.walk(tree)
    )
    if not imports_module:
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "manim":
                problems.append(
                    {
                        "line": node.lineno,
                        "call": f"manim.{node.attr}",
                        "problem": "the name 'manim' is not defined: `from manim import *` imports the "
                        "contents, not the module itself",
                        "fix": f"write {node.attr} directly, or add `import manim` as well",
                    }
                )
                break  # one report is enough; the fix is the same everywhere

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        supplied = [kw.arg for kw in node.keywords if kw.arg]
        if not supplied:
            continue

        # Constructor call:  Axes(...), MathTex(...)
        if isinstance(node.func, ast.Name) and node.func.id in index["classes"]:
            cls = index["classes"][node.func.id]
            accepted, permissive = _accepted_by_class(cls)
            if permissive:
                # Manim chains **kwargs to Mobject; the MRO union is still a real allowlist.
                accepted |= {"color", "stroke_width", "fill_opacity", "font_size", "opacity"}
            for kw in supplied:
                if kw not in accepted:
                    problems.append(
                        {
                            "line": node.lineno,
                            "call": f"{node.func.id}(...)",
                            "problem": f"unexpected keyword argument {kw!r}",
                            "valid": sorted(accepted)[:40],
                            "did_you_mean": get_close_matches(kw, sorted(accepted), n=3),
                        }
                    )
            continue

        # Method call:  axes.get_secant_slope_group(...). The receiver's type is
        # unknown statically, so check against every Manim class defining that name.
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            owners = index["methods"].get(method)
            if not owners:
                close = get_close_matches(method, list(index["methods"]), n=3)
                problems.append(
                    {
                        "line": node.lineno,
                        "call": f".{method}(...)",
                        "problem": f"no Manim class defines a method named {method!r}",
                        "did_you_mean": close,
                    }
                )
                continue
            accepted: set[str] = set()
            permissive = False
            for owner in owners:
                names, takes_kwargs = _params(getattr(index["classes"][owner], method))
                accepted.update(names)
                permissive = permissive or takes_kwargs
            if permissive:
                continue
            for kw in supplied:
                if kw not in accepted:
                    problems.append(
                        {
                            "line": node.lineno,
                            "call": f".{method}(...)",
                            "problem": f"unexpected keyword argument {kw!r}",
                            "defined_on": owners[:4],
                            "valid": sorted(accepted),
                            "did_you_mean": get_close_matches(kw, sorted(accepted), n=3),
                        }
                    )

    return {"valid": not problems, "problems": problems}
