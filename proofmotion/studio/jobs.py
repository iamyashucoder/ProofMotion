"""Bounded workers for everything that spawns a Manim process.

Rendering used to happen wherever the request happened to be: units one after
another inside the turn, and posters in as many threads as the filmstrip had
thumbnails — a cold twenty-slide deck was twenty Manim processes at once. One
pool bounds all of it, so the machine renders a few things quickly instead of
everything at a crawl.
"""

from __future__ import annotations

import contextvars
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from proofmotion.studio import render
from proofmotion.studio.document import Slide

#: Two parallel Manim renders is a lot of CPU already; more mostly trades
#: latency of the first clip for contention on all of them.
DEFAULT_WORKERS = 2


class RenderPool:
    """One bounded executor for unit renders and posters alike."""

    def __init__(self, max_workers: int = DEFAULT_WORKERS) -> None:
        self._pool = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="render")

    def run(self, thunks: list[Callable[[], Any]]) -> list[Any]:
        """Run thunks on the pool and return their results in order.

        Each thunk carries its caller's context, so events it emits stay
        stamped with the project the work belongs to.
        """
        futures = [
            self._pool.submit(contextvars.copy_context().run, thunk) for thunk in thunks
        ]
        return [future.result() for future in futures]

    def poster(
        self, slide: Slide, directory: Path, *, style: str = "dark", quality: str = "l"
    ) -> Path | None:
        """Render one slide's still on the pool; a cached one skips the queue."""
        cached = render.poster_path(slide, directory, style=style, quality=quality)
        if cached.is_file() and cached.stat().st_size:
            return cached
        job = contextvars.copy_context()
        return self._pool.submit(
            job.run, lambda: render.poster(slide, directory, style=style, quality=quality)
        ).result()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
