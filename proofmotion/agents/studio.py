"""Turn a message from the person into edits to the project.

The one-shot director designs a whole storyboard from nothing. This agent is
given a document that already exists and asked what should change — which is a
different and much smaller job. "Now show what happens as n grows" is two added
slides, not a restated answer.

Keeping it small is the point twice over. Slides already rendered keep their
content hash and so keep their clips, and a handful of operations is structured
output a model can actually finish: the storyboard schema is where a 36B local
model ran out of budget mid-JSON.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from proofmotion.runtime.loop import run_structured
from proofmotion.studio.document import Project
from proofmotion.studio.operations import Edit
from proofmotion.tools import toolset

log = logging.getLogger(__name__)

SYSTEM = """You edit a slide deck that explains mathematics and physics visually.

You are given the deck as it stands and a message from the person watching it.
Answer with the smallest set of operations that does what they asked.

Change as little as possible. Slides you do not mention keep their rendered
video exactly as it is; a slide you touch is rendered again. Rewriting a slide
that did not need to change costs the person time and gains nothing.

Never touch a locked slide. They have settled it. If it needs to change, say so
in your reply and leave it alone.

Every slide shows something. A viewer should follow the deck with the sound
off, so the figure is the slide and the algebra annotates it. Call
component_search to see the whole catalogue — read past the top of the ranking,
because the component you want is often further down under a name you would not
have searched for. Call component_build to check parameters before you commit
to them; it builds the real geometry and reports collisions.

A slide with no component is allowed when the mathematics genuinely has no
picture, and then it needs a title and a caption. It is the exception, not the
habit.

Connect the slides. Explaining is mostly showing how one step follows from the
last, and a deck of true statements in a row is not an explanation. Give a
slide a `bridge` — a few words carrying the previous step into this one:
"halve the width again", "substituting that back", "so the total is". A slide
that opens a new idea needs none; a slide continuing an argument almost always
does.

Consecutive slides on the same figure keep it on screen with the previous
equation beside them, so build a run when the argument stays with one picture
rather than restating it. Changing the parameters of the figure you are
already on is what makes it move.

Operations:
  add            — a new slide; `after` places it, empty means at the end
                   You cannot know the id of a slide you are adding: ids belong
                   to the deck. Adding several? Leave `after` empty on all of
                   them and they land in the order you wrote them.
  edit           — change a slide's title, component, parameters, caption, seconds
  set_parameter  — change one parameter, leaving the rest alone
  reorder        — move a slide after another, or to the end
  delete         — remove a slide
  lock           — mark a slide settled, or release it

Prefer set_parameter to edit when only one value changes: it is clearer in the
transcript and it says exactly what you meant.

Some asks are not edits. "Now do the second part", "explain why that is true",
a fresh question — those need the mathematics worked out and verified before
any slide can be right, and you do not have the tools to do that here. Set
needs_full_derivation and leave operations empty; the full pipeline runs
instead. Guessing at mathematics you have not derived is how a deck becomes
confident and wrong.

Adding a slide that repeats a figure already on screen with different
parameters is an edit. Adding a slide about mathematics nobody has derived is
not.

When a scene needs something drawn or moved that no component expresses,
describe it in needs_hand_drawn and leave operations empty. The coder writes
it with the Manim API available to look up and the layout checker to measure
against, none of which you have here. Do not write scene code yourself.

Give a `reason` of a few words on each operation, and a `reply` of one or two
sentences to the person. Say what you changed, not what you were asked."""


def _describe(project: Project) -> str:
    """The deck as the model needs to see it: identity, content, and lock state."""
    return json.dumps(
        {
            "question": project.question,
            "revision": project.revision,
            "total_seconds": project.seconds(),
            "slides": [
                {
                    "id": s.id,
                    "title": s.title,
                    "component": s.component,
                    "parameters": s.parameters,
                    "caption": s.caption,
                    "seconds": s.seconds,
                    "locked": s.locked,
                }
                for s in project.slides
            ],
        },
        indent=2,
        default=str,
    )


def propose(client: Any, project: Project, message: str, *, max_iterations: int = 6) -> Edit:
    """What should change, given the deck and what the person said."""
    deck = _describe(project) if project.slides else "(the deck is empty)"
    return run_structured(
        client,
        SYSTEM,
        (
            f"The deck so far:\n{deck}\n\n"
            f"The person says:\n{message}\n\n"
            "Answer with the operations that do what they asked."
        ),
        toolset("visual").subset(["component_search", "component_build", "typeset_check"]),
        Edit,
        max_iterations=max_iterations,
        max_tokens=6000,
        agent_name="studio",
    )
