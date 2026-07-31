"""A deck that cannot leave is a demo: the PDF, the zip, and their cache.

Everything here is keyed by the deck's content digest, so exporting twice
costs once — and a deck that changed gets a new file rather than a stale one.
The PDF is only written when every slide posterised; a silently thinner deck
would read as complete to whoever receives it.
"""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from proofmotion.runtime.registry import ToolError
from proofmotion.studio import render
from proofmotion.studio.document import Project


def deck_digest(project: Project) -> str:
    """The whole deck's content, in order, as one short key."""
    style, quality = render._look_of(project)
    per_slide = [
        render.digest_of([slide], style=style, quality=quality) for slide in project.slides
    ]
    return hashlib.sha256("\n".join(per_slide).encode()).hexdigest()[:16]


def ensure_posters(
    project: Project, directory: Path
) -> tuple[dict[str, Path], list[str]]:
    """Every slide's still, rendering the missing ones; failures are named.

    The per-slide poster cache makes a second sweep cost nothing.
    """
    style, quality = render._look_of(project)
    posters: dict[str, Path] = {}
    problems: list[str] = []
    for slide in project.slides:
        made = render.poster(slide, directory, style=style, quality=quality)
        if made is None:
            problems.append(f"{slide.id}: no poster could be rendered")
        else:
            posters[slide.id] = made
    return posters, problems


def posters_pdf(project: Project, directory: Path) -> Path:
    """One full-bleed page per slide, in deck order."""
    if not project.slides:
        raise ToolError("the project has no slides yet")
    directory = Path(directory)
    destination = directory / "export" / f"deck-{deck_digest(project)}.pdf"
    if destination.is_file() and destination.stat().st_size:
        return destination

    posters, problems = ensure_posters(project, directory)
    if problems:
        raise ToolError("the deck did not fully posterise: " + "; ".join(problems))

    from PIL import Image

    pages = [Image.open(posters[s.id]).convert("RGB") for s in project.slides]
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = destination.with_name(destination.name + ".tmp")
    pages[0].save(scratch, format="PDF", save_all=True, append_images=pages[1:])
    for page in pages:
        page.close()
    scratch.replace(destination)
    return destination


def bundle(project: Project, directory: Path) -> Path:
    """The video, the PDF, and the document itself, in one zip."""
    directory = Path(directory)
    video = directory / "video.mp4"
    if not video.is_file():
        raise ToolError("no video has been rendered yet")
    document = directory / "project.json"
    if not document.is_file():
        raise ToolError("the project has no saved document")
    pdf = posters_pdf(project, directory)

    destination = directory / "export" / f"{project.project_id}-{deck_digest(project)}.zip"
    if destination.is_file() and destination.stat().st_size:
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = destination.with_name(destination.name + ".tmp")
    with zipfile.ZipFile(scratch, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(video, "video.mp4")
        archive.write(pdf, "deck.pdf")
        archive.write(document, "project.json")
    scratch.replace(destination)
    return destination
