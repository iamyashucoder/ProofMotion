"""One message against one document: which agent answers, and in what order.

This is the studio's routing policy, and every branch in it is a scar. The
order of the fallbacks decides what a person sees when a turn wobbles, so the
ladder lives here as plain functions over (client, project, message) — no
HTTP, no disk, no locks — where each rung can be held still by a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from proofmotion.runtime.events import headline
from proofmotion.studio.document import Project
from proofmotion.studio.operations import Edit


@dataclass
class TurnResult:
    """What a turn decided, before anything is applied or rendered."""

    edit: Edit
    #: Set when the turn refuses outright: nothing is applied, nothing is
    #: rendered, and this text is the whole answer.
    refusal: str = ""


def run_turn(
    client: Any, project: Project, message: str, *,
    remake_slide: str = "", images: list[str] | None = None,
) -> TurnResult:
    """Answer one message: the whole pipeline for an opening question, edits after."""
    if not project.slides:
        return open_question_turn(client, project, message, images=images)
    return follow_up_turn(client, project, message, remake_slide=remake_slide, images=images)


def open_question_turn(
    client: Any, project: Project, message: str, *, images: list[str] | None = None,
) -> TurnResult:
    """An opening question gets the whole pipeline: read it, derive the
    mathematics with symbolic tools, verify, storyboard, and map every scene
    onto a component. The edit agent answers an opening question with one
    slide, and one slide is not an explanation."""
    from proofmotion.agents.studio import propose
    from proofmotion.studio.compose_full import answer_fully, derive_anyway, draw_by_hand

    operations, reply = answer_fully(client, project, message, images=images)
    if operations:
        return TurnResult(Edit(operations=operations, reply=reply))

    # Nothing to derive, or nothing came of it. A request to animate something
    # has no mathematics behind it, and forcing the pipeline through anyway
    # produced eight verified steps and ten slides that drew nothing.
    headline("Designing scenes for it")
    edit = propose(client, project, message, images=images)
    if edit.needs_hand_drawn:
        operations, reply = draw_by_hand(client, edit.needs_hand_drawn)
        return TurnResult(Edit(operations=operations, reply=reply))
    if not edit.operations:
        # An empty answer is a turn that went wrong, not proof the catalogue
        # is empty. Treating the two as the same sent every wobble straight to
        # a hand-drawn scene: asked about projectile motion — a component that
        # exists and that this same agent finds when asked again — it drew a
        # square. So the full pipeline gets a turn first, because its director
        # searches the catalogue properly.
        headline("Nothing came back; working it through instead")
        operations, reply = derive_anyway(client, project, message, images=images)
        if not operations:
            # Only now, with both routes spent.
            operations, reply = draw_by_hand(client, message)
        return TurnResult(Edit(operations=operations, reply=reply))
    return TurnResult(edit)


def follow_up_turn(
    client: Any, project: Project, message: str, *,
    remake_slide: str = "", images: list[str] | None = None,
) -> TurnResult:
    """The deck exists, so edits are edits — and escalations are deliberate."""
    from proofmotion.agents.studio import propose
    from proofmotion.studio.compose_full import answer_fully, draw_by_hand

    headline("Thinking about what to change")
    edit = propose(client, project, message, images=images)
    if edit.needs_hand_drawn:
        # Honoured on an existing deck too. It was only checked when the deck
        # was empty, so on a deck with slides the agent raised the flag,
        # nothing read it, and its reply went out unchanged: "I'll flag this
        # for a hand-drawn scene" — four times in a row, to someone asking
        # four times for the same drawing.
        operations, reply = draw_by_hand(
            client, edit.needs_hand_drawn,
            existing=edit.operations, replacing=remake_slide,
        )
        return TurnResult(Edit(operations=operations, reply=reply))
    if edit.needs_full_derivation and not remake_slide:
        # The ask needs mathematics worked out, not a slide tweaked. A tweak
        # agent inventing derivations is how a deck becomes confident and
        # wrong.
        headline("This needs working out; running the full pipeline")
        operations, reply = answer_fully(client, project, message, images=images)
        return TurnResult(Edit(operations=operations, reply=reply))
    if edit.needs_full_derivation:
        # Escalating from a remake box loses the one thing that box means.
        # Asked "how do we find pi?" on slide 4, it derived pi and appended
        # nine slides about Monte Carlo to the end of a deck about a ramp —
        # every operation valid, the slide untouched, the deck ruined.
        return TurnResult(Edit(), refusal=(
            "That needs working out from scratch rather than editing this slide. "
            "Ask it in the main box to add it here, or start a new chat for a "
            "separate explanation."
        ))
    return TurnResult(edit)
