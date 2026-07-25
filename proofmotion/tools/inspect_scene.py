"""Measure what a scene actually puts on screen, without rendering it.

The layout tools check hypothetical boxes while a storyboard is being planned.
Nothing checked the code that was finally written, which is why text kept
overlapping even though every run reported the layout as clear.

This executes the scene with animations skipped to their end state, then reports
real bounding boxes beat by beat. It is fast because nothing is rasterised or
encoded — only geometry is computed.

Text-versus-text overlap is what gets flagged. Shapes are expected to overlap
(a dot rides on a curve, a label sits inside a box); two pieces of text sharing
pixels is almost always a defect.
"""

from __future__ import annotations

import importlib.util
import logging
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any

from proofmotion.runtime.registry import ToolError, tool

log = logging.getLogger(__name__)

#: Below this height in scene units, text is genuinely unreadable in the final
#: render. The frame is 8 units tall at 1080p, so 0.14 units is about 19px.
#: Calibrated, not guessed: MathTex at font_size 24 measures 0.221 and reads
#: fine, so an earlier 0.22 cutoff flagged every axis tick label as broken.
#: font_size 12 measures 0.111 and is the case worth catching.
MIN_TEXT_HEIGHT = 0.14
SAFE_MARGIN = 0.25


def _is_text(mobject: Any) -> bool:
    from manim import DecimalNumber, MarkupText, MathTex, SingleStringMathTex, Tex, Text

    # DecimalNumber must be here: Manim builds axis tick labels from it, and
    # without it descent continued into per-glyph submobjects, so every minus
    # sign on a negative tick was reported as unreadable text 0.015 units tall.
    types: tuple[type, ...] = (Text, MarkupText, MathTex, Tex, SingleStringMathTex, DecimalNumber)
    try:
        from manim import Typst, TypstMath

        types = (*types, Typst, TypstMath)
    except ImportError:
        pass
    return isinstance(mobject, types)


def _text_units(mobject: Any, found: list[Any] | None = None) -> list[Any]:
    """Text-bearing mobjects anywhere in the tree, without splitting them apart.

    Axis labels arrive as VGroups, so checking only top-level mobjects missed the
    single most common collision: an axis label drawn over an equation. Descent
    stops at a text object, since splitting MathTex into glyphs would report every
    expression as overlapping itself.
    """
    found = [] if found is None else found
    if _is_text(mobject):
        found.append(mobject)
        return found
    for child in getattr(mobject, "submobjects", ()) or ():
        _text_units(child, found)
    return found


def _label(mobject: Any) -> str:
    text = getattr(mobject, "text", None) or getattr(mobject, "tex_string", None) or ""
    text = " ".join(str(text).split())
    return f"{type(mobject).__name__}({text[:34]})" if text else type(mobject).__name__


def _box(mobject: Any) -> dict[str, float]:
    from manim import DOWN, LEFT, RIGHT, UP

    return {
        "left": float(mobject.get_edge_center(LEFT)[0]),
        "right": float(mobject.get_edge_center(RIGHT)[0]),
        "bottom": float(mobject.get_edge_center(DOWN)[1]),
        "top": float(mobject.get_edge_center(UP)[1]),
        "height": float(mobject.height),
        "width": float(mobject.width),
    }


def _overlap(a: dict[str, float], b: dict[str, float]) -> tuple[float, float]:
    return (
        min(a["right"], b["right"]) - max(a["left"], b["left"]),
        min(a["top"], b["top"]) - max(a["bottom"], b["bottom"]),
    )


def _load_scene_class(code: str):
    """Import the generated module and return its GeneratedScene class."""
    directory = Path(tempfile.mkdtemp(prefix="pm_inspect_"))
    module_path = directory / f"scene_{uuid.uuid4().hex[:8]}.py"
    module_path.write_text(code, encoding="utf-8")
    spec = importlib.util.spec_from_file_location(module_path.stem, module_path)
    if spec is None or spec.loader is None:
        raise ToolError("could not load the generated scene module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as error:
        raise ToolError(f"the scene failed to import: {type(error).__name__}: {error}") from error
    scene_class = getattr(module, "GeneratedScene", None)
    if scene_class is None:
        raise ToolError("no GeneratedScene class in the supplied code")
    return scene_class


@tool
def inspect_scene(code: str) -> dict[str, Any]:
    """Run a scene without rendering and report what is actually on screen.

    Reports, per beat: text that overlaps other text, anything outside the frame,
    and text too small to read. Call this before finishing, and fix what it
    reports — it measures the code you wrote, not the layout you planned.

    Args:
        code: The complete Manim scene source.
    """
    from manim import Animation, config, tempconfig

    scene_class = _load_scene_class(code)
    beats: list[dict[str, Any]] = []

    class Inspector(scene_class):  # type: ignore[valid-type,misc]
        """Skips animations to their end state and records the resulting geometry."""

        def play(self, *animations: Any, **kwargs: Any) -> None:
            # Order matters, and getting it wrong hid every FadeOut: Manim adds an
            # animation's mobject before running it and cleans up afterwards. Adding
            # after clean_up resurrects everything a scene tried to remove.
            settled = []
            for animation in animations:
                if not isinstance(animation, Animation):
                    continue
                mobject = getattr(animation, "mobject", None)
                if mobject is not None and mobject not in self.mobjects:
                    self.add(mobject)
                try:
                    animation.begin()
                    animation.interpolate(1.0)
                    animation.finish()
                except Exception as error:  # noqa: BLE001 - one odd animation must not sink the check
                    log.debug("could not settle %s: %s", type(animation).__name__, error)
                    continue
                settled.append(animation)
            for animation in settled:
                try:
                    animation.clean_up_from_scene(self)
                except Exception as error:  # noqa: BLE001
                    log.debug("clean_up failed for %s: %s", type(animation).__name__, error)
            self._record()

        def wait(self, *args: Any, **kwargs: Any) -> None:
            return None

        def _record(self) -> None:
            items: list[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for top in self.mobjects:
                # Text is collected from anywhere in the tree; frame bounds are
                # checked against the top-level object the scene actually placed.
                for unit in _text_units(top):
                    if id(unit) in seen_ids or not float(getattr(unit, "width", 0)):
                        continue
                    seen_ids.add(id(unit))
                    items.append({"label": _label(unit), "text": True, **_box(unit)})
                if not _is_text(top) and float(getattr(top, "width", 0)) and id(top) not in seen_ids:
                    seen_ids.add(id(top))
                    items.append({"label": _label(top), "text": False, **_box(top)})
            beats.append({"index": len(beats) + 1, "items": items})

    with tempconfig({"dry_run": True, "disable_caching": True}):
        scene = Inspector()
        try:
            scene.construct()
        except Exception as error:  # noqa: BLE001 - reported, so the agent can fix it
            return {
                "ok": False,
                "beats": len(beats),
                "error": f"{type(error).__name__}: {error}",
                "advice": "The scene raises before it finishes. Fix this first.",
            }

    half_width, half_height = float(config.frame_width) / 2, float(config.frame_height) / 2
    overlaps: list[dict[str, Any]] = []
    offscreen: list[dict[str, Any]] = []
    unreadable: list[dict[str, Any]] = []
    seen: set[tuple[int, str, str]] = set()

    for beat in beats:
        texts = [i for i in beat["items"] if i["text"]]
        for n, first in enumerate(texts):
            for second in texts[n + 1 :]:
                dx, dy = _overlap(first, second)
                if dx > 0.02 and dy > 0.02:
                    key = (beat["index"], first["label"], second["label"])
                    if key in seen:
                        continue
                    seen.add(key)
                    overlaps.append(
                        {
                            "beat": beat["index"],
                            "between": [first["label"], second["label"]],
                            "overlap": [round(dx, 3), round(dy, 3)],
                        }
                    )
        for item in beat["items"]:
            sides = [
                side
                for side, bad in (
                    ("left", item["left"] < -half_width + SAFE_MARGIN),
                    ("right", item["right"] > half_width - SAFE_MARGIN),
                    ("bottom", item["bottom"] < -half_height + SAFE_MARGIN),
                    ("top", item["top"] > half_height - SAFE_MARGIN),
                )
                if bad
            ]
            if sides:
                offscreen.append({"beat": beat["index"], "label": item["label"], "sides": sides})
            # Glyphs with no alphanumerics (a minus sign, a bracket) are legitimately
            # short; their height says nothing about whether the text is readable.
            has_content = any(c.isalnum() for c in item["label"])
            if item["text"] and has_content and item["height"] < MIN_TEXT_HEIGHT:
                unreadable.append(
                    {"beat": beat["index"], "label": item["label"], "height": round(item["height"], 3)}
                )

    problems = len(overlaps) + len(offscreen) + len(unreadable)
    advice = []
    if overlaps:
        advice.append("Move overlapping text onto separate rows, or fade the earlier one out before the next appears.")
    if offscreen:
        advice.append(f"Keep everything within {SAFE_MARGIN} units of the frame edge; scale it down if needed.")
    if unreadable:
        advice.append(f"Raise font_size so text is at least {MIN_TEXT_HEIGHT} units tall.")

    return {
        "ok": problems == 0,
        "beats": len(beats),
        "text_overlaps": overlaps[:20],
        "out_of_frame": offscreen[:20],
        "unreadable_text": unreadable[:20],
        "advice": " ".join(advice) or "Nothing on screen overlaps, escapes the frame, or is too small.",
    }
