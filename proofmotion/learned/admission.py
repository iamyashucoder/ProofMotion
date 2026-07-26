"""What a learned component must survive before anything may use it.

A learned component is different from generated scene code in one way that
matters: scene code runs once and its damage is one video, while a learned
component is kept and reached for again. A bad one poisons every run after it.
So the gate is deliberately strict, and everything it checks is checked by
building the thing and measuring the result rather than by reading the source
and hoping.

On the static screen, honestly: it is a screen, not a sandbox. Python cannot be
made safe against source that is trying to escape, and pretending otherwise
would be worse than saying so. What it does do is catch a component that reaches
for the filesystem or the network — which is the realistic failure here, a model
writing `open(...)` to cache something, not an adversary. The trust boundary is
the same one the pipeline already crosses when it renders generated scene code.
"""

from __future__ import annotations

import ast
import types
from dataclasses import dataclass, field
from typing import Any

#: Modules a component legitimately needs. Everything a component does is build
#: mobjects and compute numbers.
ALLOWED_IMPORTS = (
    "manim",
    "numpy",
    "math",
    "cmath",
    "itertools",
    "functools",
    "operator",
    "statistics",
    "typing",
    "dataclasses",
    "pydantic",
    "sympy",
    "scipy",
    "colour",
    "proofmotion.components.base",
    "proofmotion.layout",
    "proofmotion.tools.numeric",
    "proofmotion.tools.symbolic",
    "__future__",
)

#: Names that exist only to reach outside the process or to defeat the screen.
#: The dynamic-attribute trio is here because a component has no honest use for
#: it, and `getattr(__builtins__, "open")` walked straight past a screen that
#: only looked at imports and attribute names.
FORBIDDEN_NAMES = frozenset({
    "eval", "exec", "compile", "open", "__import__", "input", "breakpoint",
    "globals", "locals", "vars", "memoryview",
    "getattr", "setattr", "delattr",
})

#: Attribute access used to walk from an object back out to the interpreter.
FORBIDDEN_ATTRS = frozenset({
    "__globals__", "__builtins__", "__subclasses__", "__bases__", "__mro__",
    "__code__", "__closure__", "__loader__", "__spec__", "__dict__",
    "__getattribute__", "__reduce__", "__reduce_ex__",
})


@dataclass
class Verdict:
    """Whether a candidate may be kept, and everything wrong with it."""

    ok: bool
    problems: list[str] = field(default_factory=list)
    parts: list[str] = field(default_factory=list)
    beats: list[list[str]] = field(default_factory=list)
    notes: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "problems": self.problems,
            "parts": self.parts,
            "beats": self.beats,
            "notes": self.notes,
        }


def _import_allowed(module: str) -> bool:
    return any(module == ok or module.startswith(ok + ".") for ok in ALLOWED_IMPORTS)


def screen_source(source: str) -> list[str]:
    """Static problems with the source, before any of it runs."""
    problems: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return [f"does not parse: {error}"]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _import_allowed(alias.name):
                    problems.append(f"line {node.lineno}: import of {alias.name!r} is not allowed")
        elif isinstance(node, ast.ImportFrom):
            # A bare `from . import x` has no module name to check.
            if node.level or node.module is None or not _import_allowed(node.module):
                problems.append(
                    f"line {node.lineno}: import from {node.module or '(relative)'!r} is not allowed"
                )
        elif isinstance(node, ast.Name) and (node.id in FORBIDDEN_NAMES or node.id in FORBIDDEN_ATTRS):
            # Checked against both sets: the escapes appear as attributes
            # (`f.__globals__`) and as bare names (`__builtins__`) alike.
            problems.append(f"line {node.lineno}: {node.id} may not be used")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_ATTRS:
            problems.append(f"line {node.lineno}: attribute {node.attr} may not be used")

    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.ClassDef | ast.FunctionDef)}
    if "Params" not in names:
        problems.append("must define a `Params` class deriving from pydantic BaseModel")
    if "build" not in names:
        problems.append("must define a `build(params)` function returning Built")
    return problems


def load_module(source: str, name: str) -> types.ModuleType:
    """Execute the source into a fresh module. Screen it first."""
    module = types.ModuleType(f"proofmotion_learned_{name}")
    exec(compile(source, f"<learned:{name}>", "exec"), module.__dict__)  # noqa: S102
    return module


def _geometry_problems(built: Any) -> list[str]:
    """The same measured gate component_build applies, on the real mobjects."""
    from manim import config

    from proofmotion.layout.collision import bounds, major_collisions

    problems = []
    for collision in major_collisions([built.group]):
        problems.append(f"text collides with geometry: {collision}")

    left, right, bottom, top = bounds(built.group)
    half_w, half_h = float(config.frame_width) / 2, float(config.frame_height) / 2
    for side, bad in (
        ("left", left < -half_w), ("right", right > half_w),
        ("bottom", bottom < -half_h), ("top", top > half_h),
    ):
        if bad:
            problems.append(f"escapes the frame on the {side}")
    return problems


def admit(source: str, name: str, example_parameters: dict[str, Any]) -> Verdict:
    """Decide whether a candidate component may be kept.

    It must screen clean, execute, validate its own example parameters, build
    real geometry, place that geometry inside the frame without text colliding
    with it, and do so identically twice.
    """
    problems = screen_source(source)
    if problems:
        return Verdict(ok=False, problems=problems)

    from manim import tempconfig
    from pydantic import BaseModel

    from proofmotion.components.base import Built

    try:
        module = load_module(source, name)
    except Exception as error:  # noqa: BLE001 - reported to the author
        return Verdict(ok=False, problems=[f"failed to load: {type(error).__name__}: {error}"])

    params_cls = getattr(module, "Params", None)
    builder = getattr(module, "build", None)
    if not (isinstance(params_cls, type) and issubclass(params_cls, BaseModel)):
        return Verdict(ok=False, problems=["`Params` must derive from pydantic BaseModel"])
    if not callable(builder):
        return Verdict(ok=False, problems=["`build` must be callable"])

    try:
        validated = params_cls.model_validate(example_parameters)
    except Exception as error:  # noqa: BLE001
        return Verdict(ok=False, problems=[f"example_parameters rejected by Params: {error}"])

    measured: list[tuple[float, ...]] = []
    built: Any = None
    with tempconfig({"dry_run": True, "disable_caching": True}):
        from proofmotion.layout.collision import bounds

        # Twice: a component that samples randomly or mutates module state
        # renders differently every time it is used, and that is not a
        # component, it is a surprise waiting for a future run.
        for attempt in range(2):
            try:
                built = builder(validated)
            except Exception as error:  # noqa: BLE001
                return Verdict(
                    ok=False,
                    problems=[f"build failed on attempt {attempt + 1}: {type(error).__name__}: {error}"],
                )
            if not isinstance(built, Built):
                return Verdict(ok=False, problems=["build must return a Built (group, parts, beats, notes)"])
            if not built.parts:
                return Verdict(ok=False, problems=["build returned no named parts; the scene cannot reveal it"])
            measured.append(tuple(round(v, 6) for v in bounds(built.group)))

        problems = _geometry_problems(built)

    if measured[0] != measured[1]:
        problems.append(f"not deterministic: bounds differed between builds, {measured[0]} then {measured[1]}")

    unknown = [b for beat in built.beats for b in beat if b not in built.parts]
    if unknown:
        problems.append(f"beats name parts that do not exist: {sorted(set(unknown))}")

    return Verdict(
        ok=not problems,
        problems=problems,
        parts=sorted(built.parts),
        beats=built.beats,
        notes=built.notes,
    )
