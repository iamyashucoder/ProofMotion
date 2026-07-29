import sys
from pathlib import Path

import pytest

from tools.manim_renderer import build_render_command, render_manim_scene


def test_builds_community_command_by_default(tmp_path: Path) -> None:
    command = build_render_command(tmp_path / "scene.py", tmp_path / "media")

    assert command[:3] == [sys.executable, "-m", "manim"]
    assert "--renderer" not in command
    assert "--media_dir" in command


def test_builds_community_opengl_command(tmp_path: Path) -> None:
    command = build_render_command(tmp_path / "scene.py", tmp_path / "media", backend="community-opengl")

    assert command[command.index("--renderer") + 1] == "opengl"


def test_builds_isolated_manimgl_command(tmp_path: Path) -> None:
    command = build_render_command(tmp_path / "scene.py", tmp_path / "media", quality="h", backend="manimgl")

    assert Path(command[0]).name == "manimgl"
    assert "-w" in command
    assert "--hd" in command
    assert command[command.index("--video_dir") + 1] == str(tmp_path / "media")


def test_rejects_unknown_backend(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Unknown render backend"):
        build_render_command(tmp_path / "scene.py", tmp_path / "media", backend="other")  # type: ignore[arg-type]


def test_reports_missing_manimgl_binary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_binary(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError

    monkeypatch.setattr("tools.manim_renderer.subprocess.run", missing_binary)
    result = render_manim_scene(tmp_path / "scene.py", tmp_path / "media", backend="manimgl")

    assert result.returncode == 1
    assert "uv sync --extra manimgl" in result.stderr
