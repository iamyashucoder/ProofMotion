import argparse
from pathlib import Path

from tools.preview_server import serve


def main() -> None:
    parser = argparse.ArgumentParser(description="Open the ProofMotion draft editor.")
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--host", default="127.0.0.1", help="Bind address. Use 0.0.0.0 to reach it from another machine.")
    parser.add_argument("--token", help="Shared secret. Auto-generated when --host is not loopback.")
    args = parser.parse_args()
    serve(args.project_dir, args.port, args.host, args.token)
