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
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from proofmotion.components import COMPONENTS
from proofmotion.compose.assembler import ScenePlan, assemble
from proofmotion.runtime.registry import ToolError
from proofmotion.studio.document import Project, Slide

log = logging.getLogger(__name__)

#: Every clip in one project must share a quality or concatenation re-encodes
#: and shows seams — which is why quality lives on the Project, in the digest,
#: and nowhere else. Manim's flags fix the pixel size and rate per letter.
QUALITY = "l"
FPS = 15
QUALITIES: dict[str, tuple[int, int, int]] = {
    "l": (854, 480, 15),
    "m": (1280, 720, 30),
    "h": (1920, 1080, 60),
}


@dataclass
class Unit:
    """Consecutive slides that share a figure, rendered as one clip."""

    slides: list[Slide]
    digest: str
    #: The figure standing on screen when this clip begins: the last slide of
    #: the previous unit, when both sides of the boundary draw one. The clip
    #: opens on it and dissolves it into its own — continuity across the cut.
    carried: Slide | None = None
    #: Whether this clip ends holding its figure for the next one to pick up.
    holds: bool = False
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


def digest_of(
    slides: list[Slide],
    *,
    style: str = "dark",
    quality: str = QUALITY,
    carried: Slide | None = None,
    holds: bool = False,
) -> str:
    """Content hash over everything that can change the pixels.

    The component's version is part of it. Improving a component in the library
    has to invalidate clips built from the old one, or an edited project
    silently mixes two generations of the same figure.

    The style is part of it only when it is not the default, and the carried
    figure and the hold only when they exist — so every project rendered
    before those features keeps its clips on upgrade.
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
            # The bridge is drawn above the caption, so it changes the pixels;
            # leaving it out meant editing only a bridge was a cache hit and
            # the old sentence stayed in the video.
            "bridge": slide.bridge,
            "code": slide.code,
        })
    key: dict = {"slides": payload, "quality": quality, "fps": FPS}
    if style != "dark":
        key["style"] = style
    if carried is not None:
        # The opening frame draws the previous unit's figure, so that figure
        # is part of this clip's pixels: editing it re-renders the seam too.
        spec = COMPONENTS.get(carried.component or "")
        key["carried"] = {
            "component": carried.component,
            "component_version": getattr(spec, "version", None),
            "parameters": carried.parameters,
            "overrides": carried.overrides,
        }
    if holds:
        key["holds"] = True
    blob = json.dumps(key, sort_keys=True, default=str)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def units_of(project: Project) -> list[Unit]:
    style, quality = _look_of(project)
    runs = group(project.slides)
    units = []
    for position, run in enumerate(runs):
        # Continuity across the cut, in both directions: this clip opens on
        # the previous figure when both sides of the boundary draw one, and
        # holds its own figure whenever the next clip will open on it.
        carried = None
        if position and _figure(run[0]) is not None:
            previous = runs[position - 1][-1]
            if _figure(previous) is not None:
                carried = previous
        holds = (
            position + 1 < len(runs)
            and _figure(run[-1]) is not None
            and _figure(runs[position + 1][0]) is not None
        )
        units.append(Unit(
            slides=run,
            digest=digest_of(run, style=style, quality=quality, carried=carried, holds=holds),
            carried=carried,
            holds=holds,
        ))
    return units


def _look_of(project: Project) -> tuple[str, str]:
    """The project's style and quality, tolerant of documents from before."""
    return getattr(project, "style", "dark") or "dark", getattr(project, "quality", QUALITY) or QUALITY


def clear_work(directory: Path) -> None:
    """Drop the transient render tree. Everything durable lives in clips/.

    Renders that succeed clean up after themselves; ones that fail leave their
    media trees behind for inspection, and those measured at many times the
    size of the clips they were scaffolding for. Opening a project is a moment
    nobody is inspecting a failure, so the whole tree goes.
    """
    shutil.rmtree(Path(directory) / "work", ignore_errors=True)


def _styled(code: str, style: str) -> str:
    """Prepend palette activation to a hand-written scene.

    The coder's hard-coded colors stay as written — they are that scene's
    content — but the background and the text defaults follow the deck.
    """
    lines = code.splitlines()
    insert = 0
    for position, line in enumerate(lines):
        if line.startswith("from __future__"):
            insert = position + 1
    prologue = [
        "from proofmotion.components.palette import activate",
        f"activate({style!r})",
    ]
    return "\n".join(lines[:insert] + prologue + lines[insert:]) + "\n"


def _render_one(unit: Unit, work: Path, clips: Path, style: str, quality: str) -> Unit:
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
            code = _styled(usable_code(hand_written[0].code), style)
        except ToolError as error:
            unit.error = f"{hand_written[0].id}: {error}"
            return unit
    else:
        try:
            code = assemble(
                unit.plan(),
                style=style,
                carried=unit.carried.as_assignment() if unit.carried else None,
                hold_stage=unit.holds,
            )
        except ToolError as error:
            unit.error = f"could not assemble {unit.ids}: {error}"
            return unit

    work.mkdir(parents=True, exist_ok=True)
    source = work / f"unit_{unit.digest}.py"
    source.write_text(code, encoding="utf-8")

    from tools.manim_renderer import render_manim_scene

    output = work / unit.digest
    result = render_manim_scene(source, output, quality=quality, timeout_seconds=300)
    produced = [p for p in output.rglob("*.mp4") if "partial_movie_files" not in p.parts]
    if result.returncode != 0 or not produced:
        # Exit code alone is not enough: Manim can exit 0 having written nothing.
        unit.error = (result.stderr or "manim exited 0 but produced no video")[-1200:]
        return unit

    clips.mkdir(parents=True, exist_ok=True)
    shutil.copy2(produced[0], destination)
    unit.clip = destination
    # The clip is the durable artifact; the media tree it came from — partial
    # movie files included — is many times its size and never read again. A
    # failed render keeps its tree so the wreckage can be inspected.
    shutil.rmtree(output, ignore_errors=True)
    source.unlink(missing_ok=True)
    return unit


def render_project(
    project: Project,
    directory: Path,
    *,
    only: list[str] | None = None,
    run: "Callable[[list[Callable[[], Unit]]], list[Unit]] | None" = None,
) -> dict:
    """Render every unit that is not already cached, and report what happened.

    Progress is published per unit. A turn takes tens of seconds and used to
    show nothing at all while it ran, which reads as a hang rather than as work
    — and the one number a person actually wants during the wait is how many
    clips are left.

    Args:
        project: The document to project.
        directory: The project directory; clips live under `clips/`.
        only: Slide ids to force a re-render of, ignoring the cache.
        run: How to execute the per-unit render thunks. The default runs them
            one after another in this thread; the studio passes a bounded pool
            so independent units render side by side.
    """
    from proofmotion.runtime.events import headline

    directory = Path(directory)
    clips, work = directory / "clips", directory / "work"
    forced = set(only or [])
    style, quality = _look_of(project)

    pending = units_of(project)
    for unit in pending:
        if forced.intersection(unit.ids):
            (clips / f"{unit.digest}.mp4").unlink(missing_ok=True)

    # One render per digest. Two identical units are one clip, and rendering
    # them side by side would have both writing the same files.
    first_of: dict[str, Unit] = {}
    for unit in pending:
        first_of.setdefault(unit.digest, unit)
    originals = list(first_of.values())

    def renderer(position: int, unit: Unit) -> "Callable[[], Unit]":
        def go() -> Unit:
            titles = ", ".join(s.title or s.id for s in unit.slides)[:60]
            if (clips / f"{unit.digest}.mp4").is_file():
                headline(f"Clip {position}/{len(originals)} reused — {titles}")
            else:
                headline(f"Rendering clip {position}/{len(originals)} — {titles}")
            done = _render_one(unit, work, clips, style, quality)
            if done.error:
                headline(
                    f"Clip {position}/{len(originals)} failed — {done.error.splitlines()[-1][:90]}",
                    "warned",
                )
            return done

        return go

    execute = run or (lambda thunks: [thunk() for thunk in thunks])
    execute([renderer(position, unit) for position, unit in enumerate(originals, 1)])

    rendered = []
    for unit in pending:
        twin = first_of[unit.digest]
        if twin is not unit:
            unit.clip, unit.cached, unit.error = twin.clip, bool(twin.clip), twin.error
        rendered.append(unit)

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
    # Joined beside the video and swapped in, so a join that dies never
    # replaces the last good video with a truncated one.
    scratch = destination.with_name(f".{destination.stem}-joining.mp4")

    if len(ordered) == 1:
        shutil.copy2(ordered[0], scratch)
        os.replace(scratch, destination)
        return destination

    listing = destination.parent / f".{destination.stem}-clips.txt"
    listing.write_text(
        "".join(f"file '{clip.resolve()}'\n" for clip in ordered), encoding="utf-8"
    )
    result = subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-c", "copy", str(scratch)],
        capture_output=True, text=True, timeout=300, check=False,
    )
    listing.unlink(missing_ok=True)
    if result.returncode != 0 or not scratch.is_file():
        scratch.unlink(missing_ok=True)
        raise ToolError(f"joining clips failed: {result.stderr[-500:]}")
    os.replace(scratch, destination)
    return destination


def build(
    project: Project,
    directory: Path,
    *,
    only: list[str] | None = None,
    run: "Callable[[list[Callable[[], Unit]]], list[Unit]] | None" = None,
) -> dict:
    """Render what changed and join everything. The whole projection.

    A failed unit does not take the video down with it. The clips that did
    render are real, so they are joined and the failure is reported against
    the slides it belongs to — one broken slide used to mean no video at all,
    which punished the eleven slides that were fine.
    """
    directory = Path(directory)
    narrated = any(s.narration.strip() for s in project.slides)
    report_extra: dict = {}
    if narrated and getattr(project, "fit_narration", False):
        # Opt-in: lengthen slides whose speech outruns them, before the units
        # are digested, so exactly the lengthened slides re-render. The caller
        # re-saves the document when this reports a change — it is an edit.
        from proofmotion.studio import narrate

        report_extra["fitted"] = narrate.fit(project, directory)

    report = render_project(project, directory, only=only, run=run)
    report.update(report_extra)
    report["partial"] = bool(report["failed"])
    report["errors"] = {
        slide_id: unit.error
        for unit in report["units"] if unit.error
        for slide_id in unit.ids
    }
    finished = [u for u in report["units"] if u.clip]
    if not finished:
        report["video"] = ""
        return report
    video = join(finished, directory / "video.mp4")
    report["video"] = str(video)
    report["seconds"] = _duration(video)

    if narrated:
        # The join writes a silent film every rebuild, so the speech is laid
        # over it here, every rebuild — one audio encode, video stream copied.
        # A deck with no narration never reaches this line.
        from proofmotion.studio import narrate

        try:
            placements, problems = narrate.audio_schedule(finished, project, directory)
            narrate.mux_narration(video, placements)
            report["narration"] = {"spoken": len(placements), "problems": problems}
        except ToolError as error:
            # The film is real without its voice; a missing TTS engine must
            # not take the video down, only say what is missing.
            report["narration"] = {"spoken": 0, "problems": [str(error)]}
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


def poster_path(
    slide: Slide, directory: Path, *, style: str = "dark", quality: str = QUALITY
) -> Path:
    """Where this slide's still lives, whether or not it exists yet.

    Exposed separately so a caller can answer "is it cached?" without paying
    for a render or holding a render worker.
    """
    return Path(directory) / "posters" / f"{digest_of([slide], style=style, quality=quality)}.png"


def poster(
    slide: Slide, directory: Path, *, style: str = "dark", quality: str = QUALITY
) -> Path | None:
    """A still of one slide, for paging through the deck like a deck.

    The video is the finished thing, but it is a poor way to work: to see slide
    seven you scrub, and scrubbing is not reading. A still per slide makes the
    deck the primary view and the video what it produces.

    Rendered with Manim's last-frame flag, so it costs a layout pass and no
    encoding, and cached against the slide's own content — a slide whose
    picture has not changed keeps its poster.
    """
    destination = poster_path(slide, directory, style=style, quality=quality)
    posters = destination.parent
    digest = destination.stem
    if destination.is_file() and destination.stat().st_size:
        return destination

    work = Path(directory) / "work"
    work.mkdir(parents=True, exist_ok=True)
    try:
        code = (
            _styled(slide.code, style)
            if slide.code
            else assemble(ScenePlan(assignments=[slide.as_assignment()]), style=style)
        )
    except ToolError as error:
        log.info("no poster for %s: %s", slide.id, error)
        return None
    code = _without_the_closing_fade(code)

    source = work / f"poster_{digest}.py"
    source.write_text(code, encoding="utf-8")

    output = work / f"poster_{digest}"
    result = subprocess.run(
        [sys.executable, "-m", "manim", "render", f"-q{quality}", "-s", "--format", "png",
         "--media_dir", str(output), str(source), "GeneratedScene"],
        capture_output=True, text=True, timeout=180, check=False,
    )
    images = sorted(output.rglob("*.png"))
    if result.returncode != 0 or not images:
        log.info("poster render failed for %s: %s", slide.id, (result.stderr or "")[-200:])
        return None

    posters.mkdir(parents=True, exist_ok=True)
    shutil.copy2(images[-1], destination)
    shutil.rmtree(output, ignore_errors=True)
    source.unlink(missing_ok=True)
    return destination
