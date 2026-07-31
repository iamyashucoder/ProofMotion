"""S9's exit criterion, measured: pictorial coverage on twenty mixed questions.

PLAN-STUDIO-II §S9: a miss on a subject component should fall to a shape, so a
mixed set of questions — some with an obvious subject component, most with
only a shape — should reach pictorial coverage above 0.8 with no subject
component added.

Costs real model calls (the full understand→plan→storyboard derivation per
question), so it is run by hand, not by CI:

    python eval/shape_coverage.py [--provider ...] [--model ...]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

#: Five with an obvious subject component, fifteen where only the shape of the
#: idea can draw it. The claim under test is that the second group no longer
#: falls to text or to a hand-drawn square.
QUESTIONS = [
    # subject components exist
    "Show the tangent line to y = x^2 sliding along the curve",
    "Riemann sums converging to the area under x^2 from 0 to 3",
    "A projectile launched at 45 degrees — show the trajectory",
    "A block sliding down a frictionless 30 degree incline",
    "Plot y = sin(x) and its derivative together",
    # sequences and processes
    "How does a large language model go from pretraining to deployment?",
    "Walk me through how RSA key generation works",
    "What happens between typing a URL and seeing the page?",
    "Explain the steps of a proof by induction",
    # comparisons
    "Compare supervised fine-tuning with reinforcement learning from human feedback",
    "Bubble sort versus merge sort — when does each win?",
    "Compare a Riemann integral with a Lebesgue integral",
    "TCP versus UDP: what does each guarantee?",
    # trees
    "Give me a taxonomy of machine learning methods",
    "How does the set of complex numbers decompose into its familiar subsets?",
    "Show the call tree of naive recursive Fibonacci for n = 5",
    # stacks
    "Explain the OSI protocol stack",
    "What are the layers of abstraction between Python code and the CPU?",
    # grids
    "Explain a confusion matrix for a binary classifier",
    "Show the state space of a game of tic-tac-toe after the first move",
]

TARGET = 0.8


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider")
    parser.add_argument("--model")
    parser.add_argument("--limit", type=int, default=len(QUESTIONS))
    args = parser.parse_args()

    from llm.providers import get_client
    from proofmotion.compose import pictorial_coverage
    from proofmotion.studio.compose_full import _plan_for

    client = get_client(args.provider, args.model)
    if client is None:
        print("No LLM provider configured.", file=sys.stderr)
        return 1

    scores: list[float] = []
    for question in QUESTIONS[: args.limit]:
        state: dict = {"force": True}
        try:
            plan = _plan_for(client, question, state)
        except Exception as error:  # noqa: BLE001 - a failed run scores zero, visibly
            print(f"  0.00  {question}  (failed: {str(error)[:80]})")
            scores.append(0.0)
            continue
        if plan is None or not plan.assignments:
            print(f"  0.00  {question}  (no scenes)")
            scores.append(0.0)
            continue
        drawn = pictorial_coverage(plan)
        used = sorted({a.component for a in plan.assignments if a.component})
        print(f"  {drawn:.2f}  {question}  ({', '.join(used) or 'nothing drawn'})")
        scores.append(drawn)

    mean = sum(scores) / len(scores) if scores else 0.0
    verdict = "PASS" if mean > TARGET else "FAIL"
    print(f"\n{verdict}: mean pictorial coverage {mean:.2f} over {len(scores)} questions (target > {TARGET})")
    return 0 if mean > TARGET else 1


if __name__ == "__main__":
    sys.exit(main())
