from pathlib import Path
import subprocess
import sys


def render_manim_scene(file_path: Path, output_dir: Path, quality: str = "l", timeout_seconds: int = 120):
    output_dir.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, "-m", "manim", f"-q{quality}", "--media_dir", str(output_dir), str(file_path), "GeneratedScene"]
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(command, 1, "", f"Rendering timed out after {timeout_seconds} seconds.")
