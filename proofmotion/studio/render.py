"""Render a project as clips, and join them.

This is where the time goes away. The video was one Manim scene, so changing
anything meant re-deriving everything: an eighteen-scene answer cost a full
render to add a nineteenth. Here each run of slides renders to its own clip,
keyed by its content, and joining them is a copy — so adding a slide costs one
slide and editing slide four leaves the other eight untouched on disk.

Clips are grouped into *runs*, not rendered one slide at a time, and that is
deliberate. The assembler holds an unchanged figure on screen across
consecutive scenes because rebuilding an identical parabola four times made the
viewer watch it flicker. Splitting those into separate clips would put a hard
cut back in the middle of the thing that fix removed. So consecutive slides
sharing a figure render together, and a boundary between runs is a place the
figure changes anyway — where a cut is what the assembler would have drawn.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from proofmotion.components import COMPONENTS
from proofmotion.compose.assembler import ScenePlan, assemble
from proofmotion.runtime.registry import ToolError
from proofmotion.studio.document import Project, Slide

log = logging.getLogger(__name__)

#: Every clip must share these or concatenation re-encodes and shows seams.
QUALITY = "l"
FPS = 15
RESOLUTION = "854x480"


@dataclass
class Unit:
    """Consecutive slides that share a figure, rendered as one clip."""

    slides: list[Slide]
    digest: str
    #: True when this unit was reused from cache rather than rendered.
    cached: bool = False
    clip: Path | None = None
    error: str = ""

    @property
    def ids(self) -> list[str]:
        return [s.id for s in self.slides]

    def plan(self) -> ScenePlan:
        """The run as a scene plan, with everything after the first continuing.

        A run is consecutive slides on one figure, which is the same thing as
        a continuing thought. Saying so keeps the figure on screen and the
        previous equation with it, instead of clearing the board between two
        steps of one argument — every slide starting from nothing is what
        makes a deck read as statements rather than an explanation.
        """
        assignments = []
        for position, slide in enumerate(self.slides):
            assignment = slide.as_assignment()
            if position:
                # The figure only. Carrying the previous equation as well put
                # three items into a caption strip under an inch tall — the
                # bridge landed across the equation it was carrying, each
                # correctly placed and collectively unreadable. Continuity of
                # the picture is what connects the steps; the equation for the
                # step just made is not needed beside the one replacing it.
                assignment.read_from_previous = ["diagram"]
            assignments.append(assignment)
        return ScenePlan(assignments=assignments)


def _figure(slide: Slide) -> tuple[str, str] | None:
    """What is drawn on the stage, or None for a text-only or hand-written slide."""
    if slide.code or not slide.component:
        return None
    # The component alone, not its parameters. Consecutive slides on one figure
    # with different numbers are a single animation — the rectangles narrowing,
    # the tangent sliding — and the assembler transforms between them. Split
    # into separate clips they become two pictures with a cut between, which is
    # the static feel this is meant to remove. The cost is a wider cache unit.
    return (slide.component, "")


def group(slides: list[Slide]) -> list[list[Slide]]:
    """Split slides into runs that share a figure.

    A run boundary is a place the picture changes, which is exactly where the
    assembler fades the stage out — so cutting there costs nothing that was not
    already a cut. Text-only slides never join a run: they clear the stage.
    """
    runs: list[list[Slide]] = []
    for slide in slides:
        figure = _figure(slide)
        if runs and figure is not None and _figure(runs[-1][-1]) == figure:
            runs[-1].append(slide)
        else:
            runs.append([slide])
    return runs


def digest_of(slides: list[Slide]) -> str:
    """Content hash over everything that can change the pixels.

    The component's version is part of it. Improving a component in the library
    has to invalidate clips built from the old one, or an edited project
    silently mixes two generations of the same figure.
    """
    payload = []
    for slide in slides:
        spec = COMPONENTS.get(slide.component or "")
        payload.append({
            "title": slide.title,
            "component": slide.component,
            "component_version": getattr(spec, "version", None),
            "parameters": slide.parameters,
            "caption": slide.caption,
            "seconds": slide.seconds,
            "overrides": slide.overrides,
            "code": slide.code,
        })
    blob = json.dumps({"slides": payload, "quality": QUALITY, "fps": FPS}, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def units_of(project: Project) -> list[Unit]:
    return [Unit(slides=run, digest=digest_of(run)) for run in group(project.slides)]


def _render_one(unit: Unit, work: Path, clips: Path) -> Unit:
    """Render a unit to its cached clip, or reuse the clip already there."""
    destination = clips / f"{unit.digest}.mp4"
    if destination.is_file() and destination.stat().st_size:
        unit.clip, unit.cached = destination, True
        return unit

    hand_written = [s for s in unit.slides if s.code]
    if hand_written:
        # A slide with its own scene is that scene. It never shares a unit, so
        # there is exactly one and nothing to assemble around it.
        #
        # Normalised here rather than only where it was written. Slides stored
        # before that check existed still carry a literal backslash-n and a
        # class the renderer never opens, and they would fail on every render
        # for the life of the project. Repairing at the point of use makes a
        # document written by an older version work.
        from proofmotion.studio.operations import usable_code

        try:
            code = usable_code(hand_written[0].code)
        except ToolError as error:
            unit.error = f"{hand_written[0].id}: {error}"
            return unit
    else:
        try:
            code = assemble(unit.plan())
        except ToolError as error:
            unit.error = f"could not assemble {unit.ids}: {error}"
            return unit

    work.mkdir(parents=True, exist_ok=True)
    source = work / f"unit_{unit.digest}.py"
    source.write_text(code, encoding="utf-8")

    from tools.manim_renderer import render_manim_scene

    output = work / unit.digest
    result = render_manim_scene(source, output, quality=QUALITY, timeout_seconds=300)
    produced = [p for p in output.rglob("*.mp4") if "partial_movie_files" not in p.parts]
    if result.returncode != 0 or not produced:
        # Exit code alone is not enough: Manim can exit 0 having written nothing.
        unit.error = (result.stderr or "manim exited 0 but produced no video")[-1200:]
        return unit

    clips.mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced[0], destination)
    unit.clip = destination
    return unit


def render_project(project: Project, directory: Path, *, only: list[str] | None = None) -> dict:
    """Render every unit that is not already cached, and report what happened.

    Progress is published per unit. A turn takes tens of seconds and used to
    show nothing at all while it ran, which reads as a hang rather than as work
    — and the one number a person actually wants during the wait is how many
    clips are left.

    Args:
        project: The document to project.
        directory: The project directory; clips live under `clips/`.
        only: Slide ids to force a re-render of, ignoring the cache.
    """
    from proofmotion.runtime.events import headline

    directory = Path(directory)
    clips, work = directory / "clips", directory / "work"
    forced = set(only or [])

    pending = units_of(project)
    rendered = []
    for position, unit in enumerate(pending, 1):
        if forced.intersection(unit.ids):
            (clips / f"{unit.digest}.mp4").unlink(missing_ok=True)
        titles = ", ".join(s.title or s.id for s in unit.slides)[:60]
        if (clips / f"{unit.digest}.mp4").is_file():
            headline(f"Clip {position}/{len(pending)} reused — {titles}")
        else:
            headline(f"Rendering clip {position}/{len(pending)} — {titles}")
        done = _render_one(unit, work, clips)
        if done.error:
            headline(f"Clip {position}/{len(pending)} failed — {done.error.splitlines()[-1][:90]}", "warned")
        rendered.append(done)

    failures = [u for u in rendered if u.error]
    return {
        "units": rendered,
        "rendered": sum(1 for u in rendered if u.clip and not u.cached),
        "reused": sum(1 for u in rendered if u.cached),
        "failed": len(failures),
        "problems": [{"slides": u.ids, "error": u.error[:400]} for u in failures],
    }


def join(units: list[Unit], destination: Path) -> Path:
    """Concatenate clips in order, without re-encoding.

    Stream copy is what keeps joining cheap — it is the difference between
    "connect the clips" and "render the video again". It only works because
    every clip was rendered at the same quality, so those settings are fixed
    here rather than passed in per call.
    """
    ordered = [u.clip for u in units if u.clip]
    if not ordered:
        raise ToolError("nothing to join: no unit produced a clip")

    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)

    if len(ordered) == 1:
        shutil.copy2(ordered[0], destination)
        return destination

    listing = destination.parent / f".{destination.stem}-clips.txt"
    listing.write_text(
        "".join(f"file '{clip.resolve()}'\n" for clip in ordered), encoding="utf-8"
    )
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(destination)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    listing.unlink(missing_ok=True)
    if result.returncode != 0 or not destination.is_file():
        raise ToolError(f"joining clips failed: {result.stderr[-500:]}")
    return destination


def build(project: Project, directory: Path, *, only: list[str] | None = None) -> dict:
    """Render what changed and join everything. The whole projection."""
    report = render_project(project, directory, only=only)
    if report["failed"]:
        report["video"] = ""
        return report
    video = join(report["units"], Path(directory) / "video.mp4")
    report["video"] = str(video)
    report["seconds"] = _duration(video)
    return report


def _duration(video: Path) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        return round(float(result.stdout.strip()), 1)
    except ValueError:
        return 0.0


def _without_the_closing_fade(code: str) -> str:
    """Drop the scene's final clearing, so the still shows the slide.

    Every assembled scene ends by fading everything out, and the still is the
    last frame — so the first posters were 854x480 of pure black, all byte
    for byte identical, which is at least an unmistakable symptom.
    """
    lines = code.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if "leaving = chrome" in lines[index]:
            return "\n".join(lines[:index]) + "\n        self.wait(0.1)\n"
    return code


def poster(slide: Slide, directory: Path) -> Path | None:
    """A still of one slide, for paging through the deck like a deck.

    The video is the finished thing, but it is a poor way to work: to see slide
    seven you scrub, and scrubbing is not reading. A still per slide makes the
    deck the primary view and the video what it produces.

    Rendered with Manim's last-frame flag, so it costs a layout pass and no
    encoding, and cached against the slide's own content — a slide whose
    picture has not changed keeps its poster.
    """
    posters = Path(directory) / "posters"
    digest = digest_of([slide])
    destination = posters / f"{digest}.png"
    if destination.is_file() and destination.stat().st_size:
        return destination

    work = Path(directory) / "work"
    work.mkdir(parents=True, exist_ok=True)
    try:
        code = slide.code or assemble(ScenePlan(assignments=[slide.as_assignment()]))
    except ToolError as error:
        log.info("no poster for %s: %s", slide.id, error)
        return None
    code = _without_the_closing_fade(code)

    source = work / f"poster_{digest}.py"
    source.write_text(code, encoding="utf-8")

    output = work / f"poster_{digest}"
    result = subprocess.run(
        [sys.executable, "-m", "manim", "render", f"-q{QUALITY}", "-s", "--format", "png",
         "--media_dir", str(output), str(source), "GeneratedScene"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    images = sorted(output.rglob("*.png"))
    if result.returncode != 0 or not images:
        log.info("poster render failed for %s: %s", slide.id, (result.stderr or "")[-200:])
        return None

    posters.mkdir(parents=True, exist_ok=True)
    shutil.copy2(images[-1], destination)
    return destination
