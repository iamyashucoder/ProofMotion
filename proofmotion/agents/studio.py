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

from proofmotion.compose.shapes import SHAPE_FIRST
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

""" + SHAPE_FIRST + """

A slide with no component is allowed when the mathematics genuinely has no
picture, and then it needs a title and a caption. It is the exception, not the
habit.

The catalogue is wider than curves and diagrams: it holds characters and
staged action — a stick-figure hero with poses and physics, a shape-shifting
geometric presence, whole scenes staged in beats. A request for characters,
a fight, a chase, or an action scene is a component request first. Hand-drawn
is claimed only after component_search has actually come back with nothing
that fits, never instead of searching.

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
  edit           — change a slide's title, component, parameters, caption,
                   seconds, or narration (the words spoken over it, never shown)
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


def _catalogue() -> str:
    """Every component's name and one-line summary, straight into the prompt.

    The agent was told to search before concluding nothing fits, and it kept
    concluding anyway — asked for a hero swinging through a built world, with
    both components sitting in the library, it answered "the catalogue has no
    component for that" without one search. A model will trust its prior over
    a tool it has not called; it cannot claim something listed in front of it
    does not exist. Names and summaries only — parameters still come from
    component_search, which stays worth calling.
    """
    from proofmotion.components import COMPONENTS

    lines = [
        f"  {spec.name} — {spec.summary}"
        for spec in sorted(COMPONENTS.values(), key=lambda s: (s.domain, s.name))
    ]
    return "The catalogue, in full:\n" + "\n".join(lines)


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
                    "narration": s.narration,
                    "locked": s.locked,
                }
                for s in project.slides
            ],
        },
        indent=2,
        default=str,
    )


def propose(
    client: Any, project: Project, message: str, *,
    max_iterations: int = 6, images: list[str] | None = None,
) -> Edit:
    """What should change, given the deck, what the person said — and showed."""
    deck = _describe(project) if project.slides else "(the deck is empty)"
    briefing = (
        f"{_catalogue()}\n\n"
        f"The deck so far:\n{deck}\n\n"
        f"The person says:\n{message}\n\n"
        "Answer with the operations that do what they asked. Call "
        "component_search for the exact parameters of anything above "
        "you intend to use."
    )
    tools = toolset("visual").subset(["component_search", "component_build", "typeset_check"])
    edit = run_structured(
        client, SYSTEM, briefing, tools, Edit,
        max_iterations=max_iterations, max_tokens=6000, agent_name="studio",
        images=images,
    )
    return _repaired(client, edit, briefing, tools, max_iterations, images=images)


def _repaired(
    client: Any, edit: Edit, briefing: str, tools: Any, max_iterations: int,
    images: list[str] | None = None,
) -> Edit:
    """One retry with the exact schemas of whatever was guessed wrong.

    Knowing a component exists is not knowing its parameters, and the agent
    reaches for plausible names instead of calling the search — its first
    math_scene arrived with invented fields, was refused at apply, and the
    person saw a refusal where a slide should be. Rejected operations come
    back here with the real schema of exactly the components they named, so
    the second answer is written against the truth rather than a guess.
    """
    from proofmotion.components import COMPONENTS
    from proofmotion.runtime.registry import ToolError
    from proofmotion.studio.operations import _check_component

    problems = []
    for operation in edit.operations:
        if operation.kind in ("add", "edit") and operation.component:
            try:
                _check_component(operation.component, operation.parameters or {})
            except ToolError as error:
                problems.append((operation.component, str(error)[:400]))
    if not problems:
        return edit

    schemas = {
        name: COMPONENTS[name].describe()
        for name, _ in problems
        if name in COMPONENTS
    }
    retry = (
        f"{briefing}\n\n"
        "Your previous operations were rejected before reaching the deck:\n"
        + "\n".join(f"- {name}: {reason}" for name, reason in problems)
        + "\n\nThese are the exact parameters of the components you named:\n"
        + json.dumps(schemas, indent=2, default=str)
        + "\n\nAnswer again with parameters that match these schemas exactly."
    )
    return run_structured(
        client, SYSTEM, retry, tools, Edit,
        max_iterations=max_iterations, max_tokens=6000, agent_name="studio",
        images=images,
    )
