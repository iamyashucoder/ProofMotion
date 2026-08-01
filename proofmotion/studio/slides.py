"""The deck as slides you step through — manim-slides is the slide maker.

The film was the only way to watch a deck, and a film cannot wait for a
person: a lecturer explaining slide four needs slide four to stay up, and a
motion worth watching once is worth looping while the room discusses it.
manim-slides owns that whole layer now — stepping, loops, speaker notes, the
HTML deck, PowerPoint — while the clips it steps through keep coming from the
studio's own renderer, because per-unit caching (edit one slide, render one
clip) is the economics that makes the studio editable at all.

Every fragment here is derived from the cached clips and named by their
digests, so a presentation rebuild after an edit re-encodes exactly the
fragments whose clips changed.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import render
from proofmotion.studio.document import Project


def _run(command: list[str], what: str, timeout: int = 300) -> None:
    result = subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)
    if result.returncode != 0:
        raise ToolError(f"{what} failed: {result.stderr[-400:]}")


def _voiced_fragment(unit, project: Project, directory: Path, folder: Path) -> Path:
    """The unit's clip with its own narration mixed in, cached by digest."""
    from proofmotion.studio import narrate

    destination = folder / f"{unit.digest}.mp4"
    if destination.is_file() and destination.stat().st_size:
        return destination

    spoken = any(s.narration.strip() for s in unit.slides)
    if not spoken:
        # Presentation players expect an audio stream; a silent one keeps the
        # slide from being the odd file out.
        _run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono",
             "-i", str(unit.clip), "-shortest", "-c:v", "copy", "-c:a", "aac", "-b:a", "64k",
             str(destination)],
            f"silencing {unit.digest}",
        )
        return destination

    placements, _ = narrate.audio_schedule([unit], project, directory)
    scratch = destination.with_name(destination.name + ".tmp.mp4")
    _run(
        narrate.mux_command(unit.clip, placements, scratch, narrate.clip_seconds(unit.clip)),
        f"voicing {unit.digest}",
    )
    os.replace(scratch, destination)
    return destination


def _reversed_fragment(voiced: Path, folder: Path, digest: str) -> Path:
    """The backward-step video manim-slides requires. Silent by design."""
    destination = folder / f"{digest}-rev.mp4"
    if destination.is_file() and destination.stat().st_size:
        return destination
    _run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(voiced),
         "-vf", "reverse", "-an", str(destination)],
        f"reversing {digest}",
    )
    return destination


def presentation(project: Project, directory: Path):
    """The deck as a manim-slides PresentationConfig, fragments and all.

    One presentation slide per unit: a unit is one continuous thought, which
    is the right place for a presenter to pause. Narration rides each
    fragment as audio and each slide as speaker notes; a slide marked `loop`
    plays its motion round while the presenter holds.
    """
    from manim_slides.config import PresentationConfig, SlideConfig

    directory = Path(directory)
    units = render.units_of(project)
    missing = [u.ids for u in units if not (directory / "clips" / f"{u.digest}.mp4").is_file()]
    if missing:
        raise ToolError(f"no clips yet for {missing}; render the deck first")
    for unit in units:
        unit.clip = directory / "clips" / f"{unit.digest}.mp4"

    folder = directory / "slides"
    folder.mkdir(parents=True, exist_ok=True)

    slides = []
    for unit in units:
        voiced = _voiced_fragment(unit, project, directory, folder)
        reverse = _reversed_fragment(voiced, folder, unit.digest)
        notes = "\n\n".join(
            f"{s.title}: {s.narration}".strip(": ")
            for s in unit.slides
            if s.title or s.narration.strip()
        )
        slides.append(SlideConfig(
            file=voiced,
            rev_file=reverse,
            loop=any(getattr(s, "loop", False) for s in unit.slides),
            notes=notes,
        ))

    px_w, px_h, _ = render.QUALITIES.get(project.quality, render.QUALITIES["l"])
    config = PresentationConfig(
        slides=slides,
        resolution=(px_w, px_h),
        background_color=_background(project),
    )
    path = folder / "presentation.json"
    config.to_file(path)
    return config, path


def _background(project: Project) -> str:
    from proofmotion.components.palette import PRESETS

    preset = PRESETS.get(getattr(project, "style", "dark") or "dark")
    return preset.background if preset else "#000000"


def _stamp(project: Project, directory: Path, suffix: str) -> Path:
    from proofmotion.studio.export import deck_digest

    return Path(directory) / "export" / f"deck-{deck_digest(project)}{suffix}"


def deck_html(project: Project, directory: Path) -> Path:
    """The whole deck as one self-contained HTML file anyone can step through."""
    from manim_slides.convert import RevealJS

    destination = _stamp(project, directory, ".html")
    if destination.is_file() and destination.stat().st_size:
        return destination
    config, _ = presentation(project, directory)
    destination.parent.mkdir(parents=True, exist_ok=True)
    RevealJS(presentation_configs=[config], one_file=True, offline=True).convert_to(destination)
    return destination


def deck_pptx(project: Project, directory: Path) -> Path:
    """The deck as PowerPoint, one video slide per unit."""
    from manim_slides.convert import PowerPoint

    destination = _stamp(project, directory, ".pptx")
    if destination.is_file() and destination.stat().st_size:
        return destination
    config, _ = presentation(project, directory)
    destination.parent.mkdir(parents=True, exist_ok=True)
    PowerPoint(presentation_configs=[config]).convert_to(destination)
    return destination
