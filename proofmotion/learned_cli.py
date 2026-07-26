"""Review what the system has taught itself.

Learned components accumulate without anyone watching, which is the point and
also the risk. This is how you look: what exists, where each came from, what it
was built with, and how to remove one that turned out to be wrong.

    proofmotion-learned                      list everything
    proofmotion-learned show <name>          provenance and source
    proofmotion-learned forget <name>        remove every version
"""

from __future__ import annotations

import argparse
import sys

from proofmotion.learned import forget, newest, read_manifest, source_of, store_dir


def _list() -> int:
    records = sorted(newest().values(), key=lambda r: r.name)
    if not records:
        print(f"No learned components yet. They will appear in {store_dir()}.")
        return 0

    history = read_manifest()
    print(f"{len(records)} learned component(s) in {store_dir()}\n")
    for record in records:
        versions = sum(1 for h in history if h.name == record.name)
        origin = f" from {record.parent}" if record.parent else ""
        print(f"  {record.name}  v{record.version}" + (f" ({versions} versions)" if versions > 1 else ""))
        print(f"    {record.summary}")
        print(f"    {record.domain}{origin}, learned {record.created_at}")
        if record.prompt:
            print(f"    for: {record.prompt[:96]}")
        print()
    return 0


def _show(name: str) -> int:
    record = newest().get(name)
    if record is None:
        print(f"No learned component named {name!r}.", file=sys.stderr)
        return 1
    print(f"{record.name} v{record.version} — {record.summary}")
    print(f"domain:  {record.domain}")
    print(f"parent:  {record.parent or '(written from scratch)'}")
    print(f"learned: {record.created_at}  in run {record.project_id or '(unknown)'}")
    print(f"for:     {record.prompt or '(no prompt recorded)'}")
    print(f"example: {record.example_parameters}")
    print(f"parts:   {', '.join(record.parts)}")
    print(f"\n--- {record.filename} ---\n")
    print(source_of(record))
    return 0


def _forget(name: str) -> int:
    removed = forget(name)
    if not removed:
        print(f"No learned component named {name!r}.", file=sys.stderr)
        return 1
    print(f"Removed {removed} version(s) of {name}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="proofmotion-learned", description=__doc__)
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("list", help="List learned components (the default).")
    show = sub.add_parser("show", help="Show one component's provenance and source.")
    show.add_argument("name")
    drop = sub.add_parser("forget", help="Remove every version of a component.")
    drop.add_argument("name")

    args = parser.parse_args()
    if args.command == "show":
        return _show(args.name)
    if args.command == "forget":
        return _forget(args.name)
    return _list()


if __name__ == "__main__":
    sys.exit(main())
