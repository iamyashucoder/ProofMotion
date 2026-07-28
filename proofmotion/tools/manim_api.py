"""Ground truth about the Manim API, queried instead of memorised.

This module exists to delete prompts.py. Manim exposes ~1200 unique methods and
~2800 valid (method, parameter) pairs; a prompt listing 47 remembered rules
covers a rounding error of that, and every rule was added only after someone hit
the bug. An agent that can look up a signature does not need to be told.
"""

from __future__ import annotations

import ast
import builtins
import functools
import inspect
from difflib import get_close_matches
from typing import Any

from proofmotion.runtime.registry import ToolError, tool


def _returns_nothing(function: ast.FunctionDef) -> bool:
    """True when a function never returns a value.

    Excludes nested definitions, whose returns belong to them.
    """
    for node in ast.walk(function):
        if node is not function and isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return) and node.value is not None:
            return False
    return True


def _void_helpers(tree: ast.AST) -> dict[str, int]:
    """Locally defined functions that build something and forget to return it.

    A recurring shape in generated scenes: a `make_letter` helper assembles a
    VGroup, omits the return, and the caller then does `.add_updater` on None.
    Nothing else here notices, and the failure only appears at render.
    """
    found: dict[str, int] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and _returns_nothing(node):
            # Only flag helpers that clearly build something; a procedure that
            # only calls self.play is meant to return nothing.
            builds = any(isinstance(inner, ast.Assign) for inner in node.body)
            if builds and not node.name.startswith(("test_", "_")):
                found[node.name] = node.lineno
    return found


def _component_beat_animation_errors(tree: ast.AST) -> list[dict[str, Any]]:
    """Find `FadeIn(part) for ... in built.beats` before Manim sees a string.

    Components deliberately expose beat *names* so a scene can choose how to
    animate their Mobjects. Treating the names themselves as Mobjects produces
    Manim's unhelpful ``Animation only works on Mobjects`` at render time.
    """
    problems: list[dict[str, Any]] = []
    animations = {"FadeIn", "FadeOut", "Create", "Write", "DrawBorderThenFill"}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.ListComp, ast.GeneratorExp)) or len(node.generators) < 2:
            continue
        beat_names = {
            generator.target.id
            for generator in node.generators
            if isinstance(generator.target, ast.Name)
            and isinstance(generator.iter, ast.Attribute)
            and generator.iter.attr == "beats"
        }
        if not beat_names:
            continue
        part_names = {
            generator.target.id
            for generator in node.generators
            if isinstance(generator.target, ast.Name)
            and isinstance(generator.iter, ast.Name)
            and generator.iter.id in beat_names
        }
        if not part_names or not isinstance(node.elt, ast.Call):
            continue
        if not (isinstance(node.elt.func, ast.Name) and node.elt.func.id in animations):
            continue
        if node.elt.args and isinstance(node.elt.args[0], ast.Name) and node.elt.args[0].id in part_names:
            problems.append(
                {
                    "line": node.lineno,
                    "call": f"{node.elt.func.id}(...)",
                    "problem": "component beats contain string part names, not Mobjects",
                    "fix": "animate built.parts[name] for each name in the beat",
                }
            )
    return problems


def _axis_config_label_errors(tree: ast.AST) -> list[dict[str, Any]]:
    """Reject ``label`` inside an axis configuration before Manim forwards it.

    ``Axes`` accepts ``x_axis_config`` and ``y_axis_config`` dictionaries, but
    their contents are forwarded to line-like Mobjects.  ``label`` sounds
    plausible, survives a constructor-signature check, and then fails deep in
    Manim as ``Mobject.__init__() got an unexpected keyword argument 'label'``.
    Axis labels must instead be distinct Mobjects from ``get_axis_labels``.
    """
    problems: list[dict[str, Any]] = []
    axes_classes = {"Axes", "ThreeDAxes", "NumberPlane", "PolarPlane"}
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in axes_classes
        ):
            continue
        for keyword in node.keywords:
            if keyword.arg not in {"axis_config", "x_axis_config", "y_axis_config"}:
                continue
            if not isinstance(keyword.value, ast.Dict):
                continue
            if any(isinstance(key, ast.Constant) and key.value == "label" for key in keyword.value.keys):
                problems.append(
                    {
                        "line": keyword.value.lineno,
                        "call": f"{node.func.id}(..., {keyword.arg}=...)",
                        "problem": "axis configuration does not accept a 'label' key",
                        "fix": "remove the label key and add labels with axes.get_axis_labels(x_label=..., y_label=...)",
                    }
                )
    return problems


def _tex_text_mode_math_errors(tree: ast.AST) -> list[dict[str, Any]]:
    """Catch superscripts/subscripts placed in text-mode ``Tex`` strings.

    ``Tex("x^2")`` fails because the caret is not inside math mode.  Generated
    subtitles often mix prose with an equation, so detect this before a costly
    render and direct the coder to split prose/Text from ``MathTex``.
    """
    problems: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "Tex"
        ):
            continue
        for argument in node.args:
            if not isinstance(argument, ast.Constant) or not isinstance(argument.value, str):
                continue
            text = argument.value
            if ("^" in text or "_" in text) and "$" not in text:
                problems.append(
                    {
                        "line": node.lineno,
                        "call": "Tex(...)",
                        "problem": "text-mode Tex contains ^ or _ outside math mode",
                        "fix": "use MathTex for the equation, or use Text for prose and keep any TeX equation in MathTex",
                    }
                )
                break
    return problems


def _bound_names(tree: ast.AST) -> set[str]:
    """Every name the module binds anywhere.

    Deliberately flat rather than scope-aware: over-collecting risks missing a
    real bug, while under-collecting flags working code, and a validator that
    cries wolf gets ignored.
    """
    bound: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, (ast.Store, ast.Del)):
            bound.add(node.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(node.name)
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for alias in node.names:
                bound.add(alias.asname or alias.name.split(".")[0])
        elif isinstance(node, ast.arg):
            bound.add(node.arg)
        elif isinstance(node, ast.ExceptHandler) and node.name:
            bound.add(node.name)
        elif isinstance(node, (ast.Global, ast.Nonlocal)):
            bound.update(node.names)
    return bound


@functools.lru_cache(maxsize=1)
def _index() -> dict[str, Any]:
    """Build a searchable index of the real Manim namespace. Cached; import is slow."""
    import manim

    classes: dict[str, type] = {}
    methods: dict[str, list[str]] = {}
    properties: dict[str, list[str]] = {}
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
        # Properties are API as well. `.animate` is the obvious one — the whole
        # `mob.animate.shift(...)` idiom goes through it — and indexing only
        # routines made the validator report every animate call as undefined.
        for member in dir(obj):
            if member.startswith("_"):
                continue
            static = inspect.getattr_static(obj, member, None)
            if isinstance(static, property) or inspect.isdatadescriptor(static):
                properties.setdefault(member, []).append(name)
    return {"module": manim, "classes": classes, "methods": methods, "properties": properties}


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
    problems.extend(_component_beat_animation_errors(tree))
    problems.extend(_axis_config_label_errors(tree))
    problems.extend(_tex_text_mode_math_errors(tree))

    # A helper that builds a mobject and forgets to return it. The caller gets
    # None, and the failure surfaces far away — always_redraw reporting that
    # NoneType has no add_updater, with nothing pointing back at the helper.
    voids = _void_helpers(tree)
    if voids:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                continue
            name = node.func.id
            if name not in voids:
                continue
            used = any(
                node in ast.walk(parent)
                for parent in ast.walk(tree)
                if isinstance(parent, (ast.Assign, ast.Call)) and parent is not node
            )
            if used:
                problems.append(
                    {
                        "line": node.lineno,
                        "call": f"{name}(...)",
                        "problem": (
                            f"{name}() never returns a value (defined at line {voids[name]}), "
                            "so this expression is None"
                        ),
                        "fix": f"add a return statement to {name}",
                    }
                )
                break

    # Receivers that are modules, not mobjects. np.zeros() is not a Manim method
    # call, and checking it against Manim's method table only produces noise.
    # `np` arrives through Manim's own star-export, so an import scan alone misses it.
    module_names = {n for n in dir(index["module"]) if inspect.ismodule(getattr(index["module"], n, None))}
    module_names |= {
        alias.asname or alias.name.split(".")[0]
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for alias in n.names
    }

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

    # Undefined names: MAGENTA is not a Manim colour, and nothing else here would
    # notice — a hallucinated constant renders as NameError minutes later.
    # Every `from X import *` contributes names *and* classes. Missing one
    # (manim.opengl, say) flags its perfectly valid API as invalid.
    star_modules = [
        n.module
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom) and n.module and any(a.name == "*" for a in n.names)
    ]
    for module_name in star_modules:
        if not (module_name == "manim" or module_name.startswith("manim.")):
            continue
        try:
            extra = __import__(module_name, fromlist=["*"])
        except ImportError:
            continue
        for name in dir(extra):
            member = getattr(extra, name, None)
            if inspect.isclass(member) and name not in index["classes"]:
                index["classes"][name] = member
                for method, _ in inspect.getmembers(member, inspect.isroutine):
                    if not method.startswith("_"):
                        index["methods"].setdefault(method, []).append(name)

    if any(m == "manim" or m.startswith("manim.") for m in star_modules):
        exported = set(dir(index["module"]))
        for module_name in star_modules:
            try:
                exported |= set(dir(__import__(module_name, fromlist=["*"])))
            except ImportError:
                continue
        known = exported | _bound_names(tree) | set(dir(builtins))
        reported: set[str] = set()
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)):
                continue
            if node.id in known or node.id in reported:
                continue
            reported.add(node.id)
            colours = sorted(n for n in exported if n.isupper() and not n.startswith("_"))
            problems.append(
                {
                    "line": node.lineno,
                    "call": node.id,
                    "problem": f"the name {node.id!r} is not defined and Manim does not export it",
                    "did_you_mean": get_close_matches(node.id, sorted(exported), n=4)
                    or get_close_matches(node.id, colours, n=4),
                }
            )

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
            if isinstance(node.func.value, ast.Name) and node.func.value.id in module_names:
                continue  # a module function, not a Manim method
            method = node.func.attr
            if method in index["properties"] and method not in index["methods"]:
                continue  # e.g. mob.animate.shift(...) goes through a property
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
