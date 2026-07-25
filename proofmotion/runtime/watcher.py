"""Watch a render in progress and publish frames as they appear.

Manim writes one partial movie file per self.play() call before concatenating
them. Polling that directory turns a silent multi-minute render into a filmstrip
that grows animation by animation, which is the difference between "is this
stuck?" and "it is on beat 7 of 9".
"""

from __future__ import annotations

import base64
import contextlib
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

from proofmotion.runtime.events import BUS

POLL_SECONDS = 1.0
THUMBNAIL_WIDTH = 360


def _thumbnail(video: Path) -> str | None:
    """Middle frame of a clip, as a base64 PNG small enough to inline in SSE."""
    try:
        result = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"thumbnail,scale={THUMBNAIL_WIDTH}:-1",
             "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"],
            capture_output=True, timeout=20, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if result.returncode != 0 or not result.stdout:
        return None
    return base64.b64encode(result.stdout).decode("ascii")


@contextlib.contextmanager
def watch_render(preview_dir: Path, label: str = "preview") -> Iterator[None]:
    """Publish a `frame` event for each partial movie Manim completes."""
    stop = threading.Event()
    seen: set[Path] = set()

    def poll() -> None:
        while not stop.is_set():
            for clip in sorted(preview_dir.rglob("partial_movie_files/**/*.mp4")):
                if clip in seen or not clip.stat().st_size:
                    continue
                seen.add(clip)
                image = _thumbnail(clip)
                if image:
                    BUS.emit("frame", index=len(seen), label=label, image=image)
            stop.wait(POLL_SECONDS)

    thread = threading.Thread(target=poll, daemon=True, name="render-watcher")
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=3)
