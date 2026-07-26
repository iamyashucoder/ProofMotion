"""Components the system writes for itself, and the gate they must pass.

A learned component is kept and reached for again, so a bad one poisons every
run after it. These tests are mostly about what admission refuses: the value is
in the rejections, not the acceptance.

No API key required.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import unittest
from pathlib import Path

logging.getLogger("manim").setLevel(logging.ERROR)

from proofmotion.components import COMPONENTS
from proofmotion.learned import admit, screen_source, store
from proofmotion.runtime.registry import ToolError
from proofmotion.tools.learned_tool import component_learn, component_source

GOOD = '''
from manim import VGroup, Line, Dot, Text

from pydantic import BaseModel, Field

from proofmotion.components.base import Built


class Params(BaseModel):
    length: float = Field(default=3.0, gt=0, le=6)
    label: str = "segment"


def build(p: Params) -> Built:
    line = Line([-p.length / 2, 0, 0], [p.length / 2, 0, 0])
    dot = Dot([p.length / 2, 0, 0])
    caption = Text(p.label, font_size=28).next_to(line, direction=[0, -1, 0], buff=0.4)
    parts = {"line": line, "dot": dot, "caption": caption}
    return Built(group=VGroup(*parts.values()), parts=parts,
                 beats=[["line"], ["dot"], ["caption"]], notes="a segment")
'''


class TestStaticScreen(unittest.TestCase):
    def test_good_source_screens_clean(self):
        self.assertEqual(screen_source(GOOD), [])

    def test_filesystem_access_is_refused(self):
        problems = screen_source(GOOD.replace("def build(p: Params) -> Built:", "def build(p):\n    open('/etc/passwd')\n") )
        self.assertTrue(any("open" in p for p in problems), problems)

    def test_subprocess_import_is_refused(self):
        problems = screen_source("import subprocess\n" + GOOD)
        self.assertTrue(any("subprocess" in p for p in problems), problems)

    def test_os_import_is_refused(self):
        problems = screen_source("import os\n" + GOOD)
        self.assertTrue(any("'os'" in p for p in problems), problems)

    def test_interpreter_escape_is_refused(self):
        """The standard walk from any object back out to the interpreter."""
        problems = screen_source(GOOD + "\nSNEAK = ().__class__.__bases__[0].__subclasses__()\n")
        self.assertTrue(any("__subclasses__" in p or "__bases__" in p for p in problems), problems)

    def test_dynamic_attribute_access_is_refused(self):
        """`getattr(__builtins__, "open")` walked past the first version.

        The screen only looked at imports and at attribute names, and
        `__builtins__` is a bare name reached through a builtin function.
        """
        for source in (
            'z = getattr(__builtins__, "open")',
            "b = __builtins__",
            'setattr(object(), "x", 1)',
        ):
            with self.subTest(source=source):
                problems = [p for p in screen_source(source) if "must define" not in p]
                self.assertTrue(problems, f"{source!r} was allowed")

    def test_the_libraries_a_component_actually_needs_are_allowed(self):
        """A screen that blocks the real work is no use either."""
        for source in (
            "import numpy as np",
            "from manim import VGroup, Line, Axes",
            "import sympy",
            "from proofmotion.layout.regions import layout, place",
            "from proofmotion.tools.numeric import numeric_sample",
        ):
            with self.subTest(source=source):
                problems = [p for p in screen_source(source) if "must define" not in p]
                self.assertEqual(problems, [], source)

    def test_missing_params_is_refused(self):
        problems = screen_source("def build(p):\n    return None\n")
        self.assertTrue(any("Params" in p for p in problems), problems)

    def test_missing_build_is_refused(self):
        problems = screen_source("from pydantic import BaseModel\n\nclass Params(BaseModel):\n    x: int = 1\n")
        self.assertTrue(any("build" in p for p in problems), problems)

    def test_unparseable_source_is_refused(self):
        self.assertTrue(screen_source("def build(:\n"))


class TestAdmission(unittest.TestCase):
    def test_a_working_component_is_admitted(self):
        verdict = admit(GOOD, "test_segment", {"length": 3.0, "label": "segment"})
        self.assertTrue(verdict.ok, verdict.problems)
        self.assertEqual(verdict.parts, ["caption", "dot", "line"])

    def test_parameters_the_model_rejects_are_reported(self):
        verdict = admit(GOOD, "test_segment", {"length": -5})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("example_parameters" in p for p in verdict.problems), verdict.problems)

    def test_a_component_that_raises_is_refused(self):
        source = GOOD.replace("line = Line(", "raise ValueError('boom')\n    line = Line(")
        verdict = admit(source, "test_boom", {"length": 3.0})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("boom" in p for p in verdict.problems), verdict.problems)

    def test_returning_something_other_than_built_is_refused(self):
        source = GOOD.replace("return Built(", "return dict(")
        verdict = admit(source, "test_notbuilt", {"length": 3.0})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("Built" in p for p in verdict.problems), verdict.problems)

    def test_a_component_with_no_named_parts_is_refused(self):
        """Unnamed pieces cannot be revealed beat by beat."""
        source = GOOD.replace('parts = {"line": line, "dot": dot, "caption": caption}', "parts = {}")
        verdict = admit(source, "test_empty", {"length": 3.0})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("no named parts" in p for p in verdict.problems), verdict.problems)

    def test_beats_naming_absent_parts_are_refused(self):
        source = GOOD.replace('beats=[["line"], ["dot"], ["caption"]]', 'beats=[["line"], ["ghost"]]')
        verdict = admit(source, "test_ghost", {"length": 3.0})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("ghost" in p for p in verdict.problems), verdict.problems)

    def test_a_nondeterministic_component_is_refused(self):
        """Randomness means a future run renders something nobody reviewed."""
        # A counter that moves the geometry on every build.
        source = GOOD.replace(
            "from proofmotion.components.base import Built",
            "from proofmotion.components.base import Built\n\n_CALLS = [0]",
        ).replace(
            "    line = Line([-p.length / 2, 0, 0], [p.length / 2, 0, 0])",
            "    _CALLS[0] += 1\n    line = Line([-p.length / 2 + _CALLS[0], 0, 0], [p.length / 2, 0, 0])",
        )
        verdict = admit(source, "test_random", {"length": 3.0})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("deterministic" in p for p in verdict.problems), verdict.problems)

    def test_a_component_that_escapes_the_frame_is_refused(self):
        source = GOOD.replace("length: float = Field(default=3.0, gt=0, le=6)", "length: float = 3.0")
        source = source.replace("[p.length / 2, 0, 0])", "[p.length / 2 + 40, 0, 0])", 1)
        verdict = admit(source, "test_escape", {"length": 3.0})
        self.assertFalse(verdict.ok)
        self.assertTrue(any("escapes the frame" in p for p in verdict.problems), verdict.problems)


class TestStore(unittest.TestCase):
    """Saving, versioning, and the names that may not be taken."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.previous = os.environ.get("PROOFMOTION_LEARNED_DIR")
        os.environ["PROOFMOTION_LEARNED_DIR"] = self.tmp.name
        self.added: list[str] = []

    def tearDown(self):
        for name in self.added:
            COMPONENTS.pop(name, None)
        if self.previous is None:
            os.environ.pop("PROOFMOTION_LEARNED_DIR", None)
        else:
            os.environ["PROOFMOTION_LEARNED_DIR"] = self.previous
        self.tmp.cleanup()

    def keep(self, name: str, **kwargs):
        self.added.append(name)
        return component_learn(
            name=name, source=GOOD, example_parameters={"length": 3.0},
            summary=kwargs.pop("summary", "a labelled segment"), **kwargs,
        )

    def test_a_kept_component_is_usable_immediately(self):
        result = self.keep("test_segment_v1")
        self.assertTrue(result["kept"], result)
        self.assertIn("test_segment_v1", COMPONENTS)

        from proofmotion.components import build
        built = build("test_segment_v1", {"length": 2.0})
        self.assertEqual(sorted(built.parts), ["caption", "dot", "line"])

    def test_a_rejected_component_is_not_saved(self):
        self.added.append("test_bad")
        result = component_learn(
            name="test_bad", source="import os\n" + GOOD,
            example_parameters={"length": 3.0}, summary="reaches for the filesystem",
        )
        self.assertFalse(result["kept"])
        self.assertNotIn("test_bad", COMPONENTS)
        self.assertEqual(store.read_manifest(), [])

    def test_a_builtin_component_cannot_be_shadowed(self):
        """Replacing a tested component with one that passed a single example."""
        with self.assertRaises(ToolError) as caught:
            store.check_name("function_plot")
        self.assertIn("built-in", str(caught.exception))

    def test_bad_names_are_refused(self):
        for name in ("", "X", "9lives", "has-dash", "Has_Capital", "a" * 60):
            with self.subTest(name=name), self.assertRaises(ToolError):
                store.check_name(name)

    def test_rewriting_bumps_the_version_and_keeps_the_old_file(self):
        self.keep("test_segment_v2")
        second = self.keep("test_segment_v2")
        self.assertEqual(second["version"], 2)
        files = sorted(p.name for p in Path(self.tmp.name).glob("*.py"))
        self.assertEqual(files, ["test_segment_v2_v1.py", "test_segment_v2_v2.py"])
        self.assertEqual(store.newest()["test_segment_v2"].version, 2)

    def test_provenance_is_recorded(self):
        self.keep("test_segment_v3", parent="function_plot", domain="calculus")
        record = store.newest()["test_segment_v3"]
        self.assertEqual(record.parent, "function_plot")
        self.assertEqual(record.domain, "calculus")
        self.assertTrue(record.created_at)
        self.assertEqual(record.example_parameters, {"length": 3.0})

    def test_an_unknown_parent_is_refused(self):
        with self.assertRaises(ToolError):
            self.keep("test_segment_v4", parent="no_such_component")

    def test_a_summary_is_required(self):
        with self.assertRaises(ToolError):
            self.keep("test_segment_v5", summary="   ")

    def test_load_all_registers_what_was_saved(self):
        self.keep("test_segment_v6")
        COMPONENTS.pop("test_segment_v6")
        self.assertEqual(store.load_all(), ["test_segment_v6"])
        self.assertIn("test_segment_v6", COMPONENTS)

    def test_a_corrupt_manifest_does_not_take_the_run_down(self):
        (Path(self.tmp.name) / "manifest.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(store.read_manifest(), [])
        self.assertEqual(store.load_all(), [])

    def test_a_component_whose_file_is_gone_is_skipped(self):
        self.keep("test_segment_v7")
        record = store.newest()["test_segment_v7"]
        (Path(self.tmp.name) / record.filename).unlink()
        COMPONENTS.pop("test_segment_v7")
        self.assertEqual(store.load_all(), [])
        # The record survives: losing it would erase what the system did.
        self.assertEqual(len(store.read_manifest()), 1)

    def test_build_resolves_a_learned_name_without_an_explicit_load(self):
        """A rendered scene runs in its own manim process, which never loaded.

        The first version failed at render time with "unknown component" while
        the same name resolved everywhere the pipeline had already loaded it.
        """
        from proofmotion.components import base

        self.keep("test_segment_lazy")
        COMPONENTS.pop("test_segment_lazy")
        previously = base._LEARNED_LOADED
        base._LEARNED_LOADED = False   # a fresh process has loaded nothing
        try:
            built = base.build("test_segment_lazy", {"length": 2.0})
        finally:
            base._LEARNED_LOADED = previously
        self.assertEqual(sorted(built.parts), ["caption", "dot", "line"])

    def test_an_unknown_name_still_raises_after_the_lazy_load(self):
        from proofmotion.components import base

        previously = base._LEARNED_LOADED
        base._LEARNED_LOADED = False
        try:
            with self.assertRaises(ToolError):
                base.build("no_such_component_anywhere", {})
        finally:
            base._LEARNED_LOADED = previously

    def test_forget_removes_every_version(self):
        self.keep("test_segment_v8")
        self.keep("test_segment_v8")
        self.assertEqual(store.forget("test_segment_v8"), 2)
        self.assertEqual(store.read_manifest(), [])
        self.assertNotIn("test_segment_v8", COMPONENTS)

    def test_the_manifest_is_readable_json(self):
        self.keep("test_segment_v9")
        raw = json.loads((Path(self.tmp.name) / "manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(raw[0]["name"], "test_segment_v9")


class TestComponentSource(unittest.TestCase):
    def test_a_builtin_component_can_be_read(self):
        result = component_source("function_plot")
        self.assertIn("class", result["params_source"])
        self.assertIn("def function_plot", result["build_source"])
        self.assertFalse(result["learned"])

    def test_an_unknown_component_raises(self):
        with self.assertRaises(ToolError):
            component_source("no_such_component")


if __name__ == "__main__":
    unittest.main()
