"""Open the studio on a project.

    proofmotion-studio                      a new project
    proofmotion-studio <project-dir>        reopen one, with its clips intact

Reopening is the point: the deck is on disk and so are the clips, so continuing
tomorrow costs nothing and renders nothing.
"""

from __future__ import annotations

import argparse
import ipaddress
import logging
import secrets
import sys
from pathlib import Path

PROJECTS = Path("studio_projects")


def _loopback(host: str) -> bool:
    if host in ("localhost", ""):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(prog="proofmotion-studio", description=__doc__)
    parser.add_argument("root", nargs="?", help="Directory of projects. Defaults to studio_projects/.")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--host", default="127.0.0.1", help="Use 0.0.0.0 to reach it from another machine.")
    parser.add_argument("--provider", help="LLM provider: deepseek, openai, ollama, openrouter, vllm.")
    parser.add_argument("--model", help="Override the provider's default model.")
    parser.add_argument("--render-workers", type=int, default=2,
                        help="How many Manim renders may run at once.")
    parser.add_argument("--token", help="Access token. Generated automatically off loopback.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    logging.getLogger("manim").setLevel(logging.ERROR)

    import uvicorn

    from llm.providers import get_client
    from proofmotion.learned import load_all as load_learned
    from proofmotion.web.app import create_app

    client = get_client(args.provider, args.model)
    if client is None:
        print(
            "No LLM provider is configured. Set a key, or use --provider ollama "
            "for a local daemon.",
            file=sys.stderr,
        )
        return 1

    learned = load_learned()
    if learned:
        print(f"Loaded {len(learned)} learned component(s).")

    directory = Path(args.root) if args.root else PROJECTS
    directory.mkdir(parents=True, exist_ok=True)

    # The studio executes generated Manim. On loopback that is your own
    # machine; on any other interface it must not be an open endpoint.
    token = args.token
    if token is None and not _loopback(args.host):
        token = secrets.token_urlsafe(16)

    app = create_app(directory, client, token=token, render_workers=args.render_workers)

    address = f"http://{args.host}:{args.port}" + (f"/?token={token}" if token else "")
    print(f"\n  Studio   {address}")
    print(f"  Projects {directory}")
    print(f"  Model    {client.name}/{client.model}\n")
    print("  Ask a question, then keep asking. Ctrl-C to stop.\n")
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    except KeyboardInterrupt:
        print("\nStopped. Reopen with:  proofmotion-studio", directory)
    return 0


if __name__ == "__main__":
    sys.exit(main())
