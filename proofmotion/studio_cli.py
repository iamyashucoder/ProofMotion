"""Open the studio on a project.

    proofmotion-studio                      a new project
    proofmotion-studio <project-dir>        reopen one, with its clips intact

Reopening is the point: the deck is on disk and so are the clips, so continuing
tomorrow costs nothing and renders nothing.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

PROJECTS = Path("studio_projects")


def main() -> int:
    parser = argparse.ArgumentParser(prog="proofmotion-studio", description=__doc__)
    parser.add_argument("project", nargs="?", help="Existing project directory. Omit for a new one.")
    parser.add_argument("--port", type=int, default=8780)
    parser.add_argument("--host", default="127.0.0.1", help="Use 0.0.0.0 to reach it from another machine.")
    parser.add_argument("--provider", help="LLM provider: deepseek, openai, ollama, openrouter, vllm.")
    parser.add_argument("--model", help="Override the provider's default model.")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )
    logging.getLogger("manim").setLevel(logging.ERROR)

    from llm.providers import LLMError, get_client
    from proofmotion.learned import load_all as load_learned
    from proofmotion.web.studio import serve_studio

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

    directory = (
        Path(args.project)
        if args.project
        else PROJECTS / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    directory.mkdir(parents=True, exist_ok=True)

    try:
        server = serve_studio(directory, client, port=args.port, host=args.host)
    except OSError as error:
        print(f"Could not open port {args.port}: {error}", file=sys.stderr)
        return 1

    print(f"\n  Studio   http://{args.host}:{args.port}")
    print(f"  Project  {directory}")
    print(f"  Model    {client.name}/{client.model}\n")
    print("  Ask a question, then keep asking. Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except (KeyboardInterrupt, LLMError):
        print("\nStopped. Reopen with:  proofmotion-studio", directory)
    finally:
        server.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
