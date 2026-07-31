"""What the person drops into the composer: images, voice, clips.

Everything lands under the project's attachments/ directory, named by content
like every other artifact here. Each kind has one honest treatment: an image
is shown to the model as pixels; a voice note becomes the words it contains,
transcribed once and cached beside the file; a video is sampled into a few
frames, because the agents reason over still mathematics, not timelines.
Nothing is silently dropped — an unsupported file or a missing transcription
key is an error that says so.
"""

from __future__ import annotations

import base64
import hashlib
import os
import subprocess
from pathlib import Path

from proofmotion.runtime.registry import ToolError

IMAGE = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
         ".webp": "image/webp", ".gif": "image/gif"}
AUDIO = {".wav", ".mp3", ".m4a", ".ogg", ".webm", ".flac"}
VIDEO = {".mp4", ".mov", ".mkv", ".avi"}

#: One message should carry a handful of pictures, not an album — every image
#: rides the prompt as base64 on every retry.
MAX_IMAGES_PER_TURN = 4
MAX_BYTES = {"image": 8 << 20, "audio": 25 << 20, "video": 120 << 20}

#: Frames sampled from a clip. Enough to see what happens; few enough to fit
#: beside the words.
VIDEO_FRAMES = 4


def kind_of(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in IMAGE:
        return "image"
    if suffix in AUDIO:
        return "audio"
    if suffix in VIDEO:
        return "video"
    raise ToolError(
        f"unsupported attachment {suffix!r}; images {sorted(IMAGE)}, "
        f"audio {sorted(AUDIO)}, video {sorted(VIDEO)}"
    )


def _attachments(directory: Path) -> Path:
    folder = Path(directory) / "attachments"
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save(directory: Path, filename: str, data: bytes) -> dict:
    """Store one upload and answer with what it became.

    Images come back as themselves; audio comes back with its transcript;
    video comes back with the ids of its sampled frames — those frames are
    what a later message actually attaches.
    """
    kind = kind_of(filename)
    if len(data) > MAX_BYTES[kind]:
        raise ToolError(f"{filename} is {len(data) >> 20}MB; the {kind} limit is {MAX_BYTES[kind] >> 20}MB")
    if not data:
        raise ToolError(f"{filename} is empty")

    suffix = Path(filename).suffix.lower()
    name = f"{hashlib.sha256(data).hexdigest()[:16]}{suffix}"
    stored = _attachments(directory) / name
    if not stored.is_file():
        scratch = stored.with_name(stored.name + ".tmp")
        scratch.write_bytes(data)
        os.replace(scratch, stored)

    entry: dict = {"id": name, "kind": kind, "bytes": len(data)}
    if kind == "audio":
        entry["transcript"] = transcribe(stored)
    elif kind == "video":
        entry["frames"] = [frame.name for frame in sample_frames(stored)]
    return entry


def data_url(directory: Path, attachment_id: str) -> str:
    """An attached image, as the data URL the model is shown."""
    suffix = Path(attachment_id).suffix.lower()
    mime = IMAGE.get(suffix)
    if mime is None:
        raise ToolError(f"{attachment_id} is not an image; only images ride a message")
    stem = Path(attachment_id).stem
    if not (len(stem) == 16 and all(c in "0123456789abcdef" for c in stem)):
        raise ToolError(f"no attachment {attachment_id!r}")
    path = _attachments(directory) / attachment_id
    if not path.is_file():
        raise ToolError(f"no attachment {attachment_id!r}")
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def sample_frames(video: Path) -> list[Path]:
    """A few evenly spaced stills; the frames are the attachment from here on."""
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(video)],
        capture_output=True, text=True, timeout=30, check=False,
    )
    try:
        seconds = float(result.stdout.strip())
    except ValueError as error:
        raise ToolError(f"could not read {video.name}: {result.stderr[-200:]}") from error

    frames = []
    for index in range(VIDEO_FRAMES):
        at = seconds * (index + 0.5) / VIDEO_FRAMES
        scratch = video.with_name(f".{video.stem}-f{index}.png")
        grab = subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{at:.2f}",
             "-i", str(video), "-frames:v", "1", str(scratch)],
            capture_output=True, text=True, timeout=60, check=False,
        )
        if grab.returncode != 0 or not scratch.is_file():
            raise ToolError(f"could not sample {video.name}: {grab.stderr[-200:]}")
        data = scratch.read_bytes()
        scratch.unlink(missing_ok=True)
        name = f"{hashlib.sha256(data).hexdigest()[:16]}.png"
        frame = video.parent / name
        if not frame.is_file():
            frame.write_bytes(data)
        frames.append(frame)
    return frames


def transcribe(audio: Path) -> str:
    """A voice note, as the words it contains. Transcribed once, cached beside it.

    Uses the OpenAI transcription endpoint with the key already configured for
    the studio's model. No key, no pretending: the error says what to set.
    """
    sidecar = audio.with_suffix(audio.suffix + ".txt")
    if sidecar.is_file():
        return sidecar.read_text(encoding="utf-8")

    if not os.environ.get("OPENAI_API_KEY"):
        raise ToolError(
            "transcription needs OPENAI_API_KEY set (the same key the openai "
            "provider uses); set it or type the message instead"
        )
    from openai import OpenAI

    model = os.environ.get("PROOFMOTION_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe")
    try:
        with open(audio, "rb") as source:
            out = OpenAI().audio.transcriptions.create(model=model, file=source)
    except Exception as error:
        raise ToolError(f"transcription failed ({model}): {str(error)[:300]}") from error
    text = (out.text or "").strip()
    if not text:
        raise ToolError("the recording transcribed to nothing — was there speech in it?")
    sidecar.write_text(text, encoding="utf-8")
    return text
