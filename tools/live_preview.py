"""Draft-first preview state. Preview metadata is editable before final render."""
import json
from pathlib import Path
from typing import Any


def write_preview_manifest(project_dir: Path, storyboard: dict[str, Any], scene_file: Path) -> Path:
    payload = {
        "mode": "draft-preview",
        "scene_file": str(scene_file),
        "storyboard": storyboard,
        "editing": {
            "workflow": "Edit storyboard.json or generated_scene.py, then rerun with --preview.",
            "editable_fields": ["scene duration", "narration", "equations", "visual objects", "camera/layout notes"],
            "final_render_requires_approval": True,
        },
    }
    path = project_dir / "preview_manifest.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (project_dir / "storyboard.json").write_text(json.dumps(storyboard, indent=2), encoding="utf-8")
    return path
