"""Speech for the slides that carry words: local, cached, never faked.

Narration is synthesized by Piper on this machine — no network, no key — and
cached by content exactly like clips: the same sentence in the same voice is
the same wav forever. When the engine or a voice is missing the error says
precisely how to get it; a deck with no narration never touches this module,
so a silent studio pays nothing.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import subprocess
import wave
from functools import lru_cache
from pathlib import Path

from proofmotion.runtime.registry import ToolError

#: Bumped when the synthesis pipeline changes in a way that alters the audio,
#: invalidating cached speech the way a component version invalidates clips.
ENGINE_VERSION = 1

DEFAULT_VOICE = "en_US-lessac-medium"


def voice_dir() -> Path:
    configured = os.environ.get("PROOFMOTION_VOICE_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[2] / "voices"


def _remedy(voice: str) -> str:
    return (
        f"install the speech extra and download the voice first:\n"
        f"  pip install 'proofmotion[speech]'\n"
        f"  python -m piper.download_voices {voice} --data-dir {voice_dir()}"
    )


@lru_cache(maxsize=4)
def _engine(voice: str):
    try:
        from piper import PiperVoice
    except ImportError as error:
        raise ToolError(f"piper-tts is not installed; {_remedy(voice)}") from error

    model = voice_dir() / f"{voice}.onnx"
    if not model.is_file():
        raise ToolError(f"the voice {voice!r} is not downloaded; {_remedy(voice)}")
    return PiperVoice.load(str(model))


def speech_digest(text: str, voice: str) -> str:
    blob = f"{ENGINE_VERSION}\n{voice}\n{text}"
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def audio_path(text: str, voice: str, directory: Path) -> Path:
    return Path(directory) / "audio" / f"{speech_digest(text, voice)}.wav"


def synthesize(text: str, voice: str, directory: Path) -> Path:
    """Text to a cached wav. The cache key is the content, not the slide."""
    text = text.strip()
    if not text:
        raise ToolError("there is nothing to say: the narration is empty")
    destination = audio_path(text, voice or DEFAULT_VOICE, directory)
    if destination.is_file() and destination.stat().st_size:
        return destination

    engine = _engine(voice or DEFAULT_VOICE)
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = destination.with_name(destination.name + ".tmp")
    with wave.open(str(scratch), "wb") as sink:
        engine.synthesize_wav(text, sink)
    os.replace(scratch, destination)
    return destination


def seconds_of(wav: Path) -> float:
    with wave.open(str(wav), "rb") as source:
        return round(source.getnframes() / float(source.getframerate() or 1), 2)


def narrate_project(project, directory: Path) -> dict[str, Path]:
    """A wav per narrated slide; every repeat is a cache hit."""
    voice = getattr(project, "voice", "") or DEFAULT_VOICE
    spoken: dict[str, Path] = {}
    for slide in project.slides:
        if slide.narration.strip():
            spoken[slide.id] = synthesize(slide.narration, voice, directory)
    return spoken


# ---- timing the words against the film -----------------------------------


def clip_seconds(clip: Path) -> float:
    """A clip's real duration, memoised beside it.

    The assembler's timing is animation-driven, so a slide's declared seconds
    is an intention rather than a measurement — the clip is the truth.
    """
    sidecar = clip.with_suffix(".json")
    if sidecar.is_file():
        try:
            return float(json.loads(sidecar.read_text(encoding="utf-8"))["seconds"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(clip)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        seconds = round(float(result.stdout.strip()), 3)
    except ValueError as error:
        raise ToolError(f"could not measure {clip.name}: {result.stderr[-200:]}") from error
    sidecar.write_text(json.dumps({"seconds": seconds}), encoding="utf-8")
    return seconds


def audio_schedule(units, project, directory: Path) -> tuple[list[tuple[Path, int]], list[str]]:
    """Where each slide's speech starts, in milliseconds into the joined film.

    Within a multi-slide unit the clip's real duration is split proportionally
    to the slides' declared seconds — the honest approximation, since exact
    per-slide offsets inside one animation do not exist. Speech longer than
    its slot is placed anyway and reported: trimming would discard words
    silently, and the report makes the fix a one-line edit.
    """
    voice = getattr(project, "voice", "") or DEFAULT_VOICE
    placements: list[tuple[Path, int]] = []
    problems: list[str] = []
    cursor = 0.0
    for unit in units:
        if not unit.clip:
            continue  # a failed unit is absent from the film, so from the timeline
        real = clip_seconds(unit.clip)
        declared = sum(s.seconds for s in unit.slides) or 1.0
        offset = cursor
        for slide in unit.slides:
            slot = real * (slide.seconds / declared)
            text = slide.narration.strip()
            if text:
                wav = synthesize(text, voice, directory)
                spoken = seconds_of(wav)
                if spoken > slot + 0.05:
                    problems.append(
                        f"narration for {slide.id} runs {spoken:.1f}s in a ~{slot:.1f}s "
                        "slot — lengthen the slide or shorten the note"
                    )
                placements.append((wav, int(round(offset * 1000))))
            offset += slot
        cursor += real
    return placements, problems


def fit(project, directory: Path) -> list[str]:
    """Opt-in: lengthen slides whose speech outruns them. A visible edit.

    The document changes — that is the point, and why it is opt-in — and only
    the lengthened slides' digests move, so exactly they re-render.
    """
    voice = getattr(project, "voice", "") or DEFAULT_VOICE
    fitted: list[str] = []
    for slide in project.slides:
        text = slide.narration.strip()
        if not text:
            continue
        need = seconds_of(synthesize(text, voice, directory)) + 0.8
        if slide.seconds < need:
            slide.seconds = min(40.0, float(math.ceil(need)))
            fitted.append(slide.id)
    return fitted


def mux_command(video: Path, placements: list[tuple[Path, int]], destination: Path) -> list[str]:
    """The one ffmpeg call: video stream copied, speech delayed and mixed.

    A pure function so the exact command is testable without running it.
    """
    command = ["ffmpeg", "-y", "-loglevel", "error", "-i", str(video)]
    for wav, _ in placements:
        command += ["-i", str(wav)]
    delayed, filters = [], []
    for index, (_, ms) in enumerate(placements, start=1):
        filters.append(f"[{index}:a]adelay={ms}|{ms}[d{index}]")
        delayed.append(f"[d{index}]")
    filters.append(f"{''.join(delayed)}amix=inputs={len(placements)}:normalize=0[mix]")
    # apad + -shortest pin the audio track to the video's length exactly.
    filters.append("[mix]apad[aout]")
    command += [
        "-filter_complex", ";".join(filters),
        "-map", "0:v", "-map", "[aout]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-shortest", str(destination),
    ]
    return command


def mux_narration(video: Path, placements: list[tuple[Path, int]]) -> Path:
    """Lay the speech over the film, in place, atomically."""
    if not placements:
        return video
    scratch = video.with_name(f".{video.stem}-spoken.mp4")
    result = subprocess.run(
        mux_command(video, placements, scratch),
        capture_output=True, text=True, timeout=300, check=False,
    )
    if result.returncode != 0 or not scratch.is_file():
        scratch.unlink(missing_ok=True)
        raise ToolError(f"mixing narration failed: {result.stderr[-500:]}")
    os.replace(scratch, video)
    return video
