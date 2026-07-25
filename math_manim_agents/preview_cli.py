import argparse
from pathlib import Path

from tools.preview_server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the local Math Manim draft editor.")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    serve(args.project_dir, args.port)
