import subprocess
import sys
from pathlib import Path
from typing import Literal

RenderBackend = Literal["community", "community-opengl", "manimgl"]


def build_render_command(
    file_path: Path,
    output_dir: Path,
    quality: str = "l",
    backend: RenderBackend = "community",
) -> list[str]:
    """Build an explicit command for one of the supported Manim engines."""
    if backend == "community":
        return [
            sys.executable, "-m", "manim", f"-q{quality}", "--media_dir", str(output_dir),
            str(file_path), "GeneratedScene",
        ]
    if backend == "community-opengl":
        return [
            sys.executable, "-m", "manim", f"-q{quality}", "--renderer", "opengl",
            "--media_dir", str(output_dir), str(file_path), "GeneratedScene",
        ]
    if backend == "manimgl":
        # ManimGL uses its own ``manimgl`` CLI and ``manimlib`` module namespace.
        quality_flag = {"l": "-l", "m": "-m", "h": "--hd", "k": "--uhd"}.get(quality, "-l")
        local_cli = Path(sys.executable).with_name("manimgl")
        executable = str(local_cli) if local_cli.is_file() else "manimgl"
        return [executable, str(file_path), "GeneratedScene", "-w", quality_flag, "--video_dir", str(output_dir)]
    raise ValueError(f"Unknown render backend: {backend}")


def render_manim_scene(
    file_path: Path,
    output_dir: Path,
    quality: str = "l",
    timeout_seconds: int = 120,
    backend: RenderBackend = "community",
):
    """Render a scene with Manim Community, Community/OpenGL, or ManimGL.

    ManimGL input must import from ``manimlib``. ProofMotion-generated scenes
    import from ``manim`` and should use either Community backend.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    command = build_render_command(file_path, output_dir, quality, backend)
    try:
        # check=False: a failed render is data the debug agent acts on, not an exception.
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 1, "", f"Rendering timed out after {timeout_seconds} seconds.")
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            command,
            1,
            "",
            "ManimGL is not installed. Run `uv sync --extra manimgl` before using backend='manimgl'.",
        )
