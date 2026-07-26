"""Rebuild demo/ from the runs in generated_projects/.

The gallery was assembled by hand, which meant it drifted out of date the moment
anything new rendered. This reads each project's own state.json, so the table
reports what the run actually recorded rather than what someone remembered.

    uv run python scripts/build_demo.py

Existing demo videos are kept: entries whose project directory has since been
deleted still have their file and their row, reconstructed from the filename.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROJECTS = ROOT / "generated_projects"
DEMO = ROOT / "demo"
SLUG_CHARS = re.compile(r"[^a-z0-9]+")

NOTES = """## Notes

- Early entries predate the layout engine and show the overlapping text that motivated it.
- Runs against several models on the same question are kept side by side deliberately;
  they are the clearest evidence of what is the system's doing and what is the model's.
- `assembled` marks scenes emitted by the deterministic assembler rather than written
  by the coding agent. Those runs skip the coder loop entirely.
"""


def slug(text: str, limit: int = 52) -> str:
    return SLUG_CHARS.sub("-", text.lower()).strip("-")[:limit].strip("-")


def duration(path: Path) -> float | None:
    """Length in seconds, or None when ffprobe cannot read the file."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
            capture_output=True, text=True, timeout=30, check=True,
        )
        return round(float(out.stdout.strip()), 1)
    except (subprocess.SubprocessError, ValueError, FileNotFoundError):
        return None


def defects(state: dict) -> int | None:
    report = state.get("layout_report") or {}
    if not report:
        return None
    return sum(
        len(report.get(key) or [])
        for key in ("text_overlaps", "out_of_frame", "unreadable_text", "text_on_ink")
    )


def video_of(project: Path) -> Path | None:
    """The finished render, preferring final quality over the preview."""
    for sub in ("final", "preview"):
        found = sorted((project / sub).rglob("*.mp4"))
        if found:
            return found[0]
    return None


def collect() -> list[dict]:
    rows: list[dict] = []
    for project in sorted(PROJECTS.iterdir()) if PROJECTS.is_dir() else []:
        state_file = project / "state.json"
        if not project.is_dir() or not state_file.is_file():
            continue
        try:
            state = json.loads(state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        video = video_of(project)
        if video is None:
            continue
        prompt = state.get("user_prompt") or "(no prompt recorded)"
        model = f"{state.get('llm_provider') or '?'}/{state.get('llm_model') or 'unknown'}"
        rows.append({
            "prompt": prompt,
            "model": model,
            "source": video,
            "name": f"{slug(prompt)}__{slug(model.split('/')[-1])}.mp4",
            "seconds": duration(video),
            "composed": bool(state.get("composed")),
            "assembled": bool(state.get("assembled")),
            "components": state.get("components_used") or [],
            "defects": defects(state),
        })
    return rows


def unique(rows: list[dict]) -> list[dict]:
    """Suffix repeated names so two runs of one question keep both videos."""
    seen: dict[str, int] = {}
    for row in rows:
        base = row["name"]
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            row["name"] = base.replace(".mp4", f"-{seen[base]}.mp4")
    return rows


def orphans(rows: list[dict]) -> list[dict]:
    """Videos already in demo/ whose project directory is gone."""
    known = {row["name"] for row in rows}
    out = []
    for path in sorted(DEMO.glob("*.mp4")):
        if path.name in known:
            continue
        question, _, model = path.stem.partition("__")
        out.append({
            "prompt": question.replace("-", " ").strip().capitalize(),
            "model": f"?/{model or 'unknown'}",
            "source": None,
            "name": path.name,
            "seconds": duration(path),
            "composed": False,
            "assembled": False,
            "components": [],
            "defects": None,
        })
    return out


def table(rows: list[dict]) -> str:
    lines = [
        "| # | Question | Model | Length | Assembled | Composed | Components | Defects |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, 1):
        question = row["prompt"].replace("\n", " ").strip()
        shown = question if len(question) <= 76 else question[:73].rstrip() + "..."
        components = ", ".join(f"`{c}`" for c in sorted(set(row["components"]))) or "—"
        length = f"{row['seconds']}s" if row["seconds"] is not None else "—"
        lines.append(
            f"| {index} | [{shown}]({row['name']}) | {row['model']} | {length} | "
            f"{'yes' if row['assembled'] else 'no'} | {'yes' if row['composed'] else 'no'} | "
            f"{components} | {row['defects'] if row['defects'] is not None else '—'} |"
        )
    return "\n".join(lines)


def main() -> int:
    if not DEMO.is_dir():
        DEMO.mkdir(parents=True)

    rows = unique(collect())
    for row in rows:
        if row["source"] is not None:
            shutil.copy2(row["source"], DEMO / row["name"])

    # Chronological: orphans are the oldest runs, whose projects are long gone,
    # and `rows` come from timestamp-named directories in order. The README's
    # claim that early entries predate the layout engine depends on this.
    everything = orphans(rows) + rows
    size = sum((DEMO / r["name"]).stat().st_size for r in everything if (DEMO / r["name"]).is_file())
    assembled = sum(1 for r in everything if r["assembled"])

    (DEMO / "README.md").write_text(
        "# Demo gallery\n\n"
        "Every animation ProofMotion has rendered, with the question that produced it.\n"
        "Nothing here was hand-edited — each is the pipeline's own output, kept whether\n"
        "it came out well or badly, because the failures are the more useful record.\n\n"
        "`composed` means the scene was built from verified components rather than\n"
        "hand-written Manim. `defects` counts what the layout checker measured on the\n"
        "finished scene: text over text, text over geometry, and anything off-frame.\n\n"
        f"{len(everything)} animations, {size / 1e6:.1f} MB, {assembled} assembled.\n\n"
        "Rebuild with `uv run python scripts/build_demo.py`.\n\n"
        f"{table(everything)}\n\n{NOTES}",
        encoding="utf-8",
    )
    print(f"{len(everything)} animations, {assembled} assembled, {size / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
