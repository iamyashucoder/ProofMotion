"""Components the system wrote for itself, kept for the next question.

The library covers what someone thought to build. Everything else falls to the
coder, which writes it once and throws it away — so the same gap is rediscovered
and re-solved on every run that touches it.

This keeps the answer. A model that has used `function_plot` and found it does
not quite express what it needs can rewrite it, and if the rewrite survives
admission it is registered immediately: usable in the run that produced it, and
in every run after. Provenance travels with it — the question that prompted it,
the component it came from, the run it was born in — because a component with no
history is one nobody can later judge.

Learned components are ordinary components once registered. `component_search`
finds them, `component_build` builds them, the assembler assembles them. There
is no second-class path, and that is the point.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from proofmotion.components.base import COMPONENTS, Component
from proofmotion.runtime.registry import ToolError

log = logging.getLogger(__name__)

DEFAULT_DIR = Path(__file__).resolve().parent.parent.parent / "learned_components"
IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{2,48}$")


def store_dir() -> Path:
    """Where learned components live. Overridable for tests and for sharing."""
    return Path(os.environ.get("PROOFMOTION_LEARNED_DIR") or DEFAULT_DIR)


@dataclass
class LearnedRecord:
    """One learned component, and where it came from."""

    name: str
    version: int
    domain: str
    summary: str
    parent: str | None
    example_parameters: dict[str, Any]
    parts: list[str] = field(default_factory=list)
    beats: list[list[str]] = field(default_factory=list)
    created_at: str = ""
    prompt: str = ""
    project_id: str = ""
    filename: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _manifest_path() -> Path:
    return store_dir() / "manifest.json"


def read_manifest() -> list[LearnedRecord]:
    path = _manifest_path()
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        log.warning("learned manifest unreadable (%s); treating the store as empty", error)
        return []
    records = []
    for entry in raw if isinstance(raw, list) else []:
        try:
            records.append(LearnedRecord(**entry))
        except TypeError:
            log.warning("skipping malformed learned entry: %s", str(entry)[:120])
    return records


def _write_manifest(records: list[LearnedRecord]) -> None:
    directory = store_dir()
    directory.mkdir(parents=True, exist_ok=True)
    _manifest_path().write_text(
        json.dumps([r.as_dict() for r in records], indent=2), encoding="utf-8"
    )


def newest() -> dict[str, LearnedRecord]:
    """The current version of each learned component, by name."""
    latest: dict[str, LearnedRecord] = {}
    for record in read_manifest():
        if record.name not in latest or record.version > latest[record.name].version:
            latest[record.name] = record
    return latest


def source_of(record: LearnedRecord) -> str:
    return (store_dir() / record.filename).read_text(encoding="utf-8")


def check_name(name: str) -> None:
    """A learned name must be a fresh identifier, never shadowing a built-in one.

    Shadowing is the dangerous case: a rewrite registered as `function_plot`
    would silently replace a component that is tested at its extremes with one
    that passed a single example, everywhere, forever.
    """
    if not IDENTIFIER.match(name or ""):
        raise ToolError(
            f"{name!r} is not a usable name: lowercase letters, digits and underscores, "
            "starting with a letter, 3-49 characters."
        )
    builtin = {n for n, spec in COMPONENTS.items() if not getattr(spec, "learned", False)}
    if name in builtin:
        raise ToolError(
            f"{name!r} is a built-in component and may not be replaced. Give the variant its "
            "own name, such as {name}_stepped, and say what it does differently in the summary."
        )


def register(record: LearnedRecord, source: str) -> Component:
    """Put a learned component into the live registry for this process."""
    from proofmotion.learned.admission import load_module

    module = load_module(source, record.name)
    spec = Component(
        name=record.name,
        version=record.version,
        domain=record.domain,
        summary=record.summary,
        params=module.Params,
        build=module.build,
    )
    # Marked so search can say where it came from and check_name can tell a
    # learned component apart from one that ships with the system.
    spec.learned = True  # type: ignore[attr-defined]
    spec.parent = record.parent  # type: ignore[attr-defined]
    COMPONENTS[record.name] = spec
    return spec


def save(
    *,
    name: str,
    source: str,
    domain: str,
    summary: str,
    example_parameters: dict[str, Any],
    parts: list[str],
    beats: list[list[str]],
    parent: str | None = None,
    prompt: str = "",
    project_id: str = "",
) -> LearnedRecord:
    """Write an admitted component to the store and register it.

    The caller is responsible for having admitted it; saving something that has
    not passed would put a component nobody has built into every future run.
    """
    records = read_manifest()
    version = max((r.version for r in records if r.name == name), default=0) + 1
    filename = f"{name}_v{version}.py"

    directory = store_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_text(source, encoding="utf-8")

    record = LearnedRecord(
        name=name,
        version=version,
        domain=domain or "learned",
        summary=summary,
        parent=parent,
        example_parameters=example_parameters,
        parts=parts,
        beats=beats,
        created_at=f"{datetime.now(UTC):%Y-%m-%dT%H:%M:%SZ}",
        prompt=prompt[:400],
        project_id=project_id,
        filename=filename,
    )
    records.append(record)
    _write_manifest(records)
    register(record, source)
    log.info("learned component %s v%s saved", name, version)
    return record


def load_all() -> list[str]:
    """Register every learned component. Returns the names that loaded.

    A component that no longer loads — because something it depended on moved —
    is skipped with a warning rather than taking the run down with it. It stays
    in the manifest, because deleting a record on a transient import error would
    lose work the system did.
    """
    loaded = []
    for name, record in sorted(newest().items()):
        try:
            register(record, source_of(record))
        except Exception as error:  # noqa: BLE001 - one bad component is not fatal
            log.warning("learned component %s v%s did not load: %s", name, record.version, error)
            continue
        loaded.append(name)
    return loaded


def forget(name: str) -> int:
    """Remove every version of a learned component. Returns how many went.

    Nothing calls this automatically. A learned component that turns out to be
    wrong is a human judgement, and the store is the record of what the system
    tried — losing that silently would be worse than keeping a bad entry.
    """
    records = read_manifest()
    keep = [r for r in records if r.name != name]
    gone = len(records) - len(keep)
    for record in records:
        if record.name == name:
            (store_dir() / record.filename).unlink(missing_ok=True)
    _write_manifest(keep)
    COMPONENTS.pop(name, None)
    return gone
