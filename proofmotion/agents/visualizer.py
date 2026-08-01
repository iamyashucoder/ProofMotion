"""The agent that finds the picture in the mathematics.

The others build the argument; this one goes back over the deck asking one
question per slide: what varies here, and against what? Anything that varies
is a function, and a function can be drawn — as a curve, a surface, a moving
point, a shaded region. A deck kept ending up mostly words because nobody's
whole job was the pictures; now somebody's is.
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

SYSTEM = """You find the picture in the mathematics of a slide deck.

You are given a finished deck. Some of its slides draw nothing — a title and
words, or algebra alone. For each one, ask: what varies here, and against
what? Anything that varies is a function, and a function can be drawn:

- y = f(x), a rate, a growth, an error over time — function_plot, or
  curve_motion when the idea is a point moving or sliding along it
- z = f(x, y), a landscape, a loss, a field over the plane — surface_plot,
  or surface_descent when something rolls downhill on it
- a geometric setup — circles, regions, chords, vectors — geometry_construction
- accumulating area, a sum becoming an integral — riemann_area, partial_sums
- a slope at a point — tangent_secant
- a distribution, a spread — distribution_plot

Answer with `edit` operations that set a component and REAL parameters on the
slides that need one — parameters computed from the slide's own mathematics,
its equations and its numbers, never placeholders. Keep the slide's title,
caption and narration unless the caption repeats what the figure now shows.

Rules:
- Never delete, reorder, or rewrite the argument. You illustrate it.
- A slide whose mathematics genuinely has no function and no figure — a pure
  definition, a naming of terms — is left alone. Do not decorate.
- An equation_chain slide stays an equation_chain when the algebra IS the
  content; illustrate it only when the equations describe something drawable
  and nothing else in the deck draws it.
- Never touch a locked slide.
- Call component_parameters once with every component you intend to use, and
  component_build to check parameters you are less than sure of.

Reply with one sentence saying what you illustrated."""


def illustrate(client: Any, project: Project, *, max_iterations: int = 6) -> Edit:
    """One pass over the deck, turning wordy slides into drawn ones."""
    from proofmotion.tools.components_tool import catalogue_text

    deck = json.dumps(
        [
            {
                "id": s.id,
                "title": s.title,
                "component": s.component,
                "parameters": s.parameters,
                "caption": s.caption,
                "narration": s.narration,
                "locked": s.locked,
            }
            for s in project.slides
        ],
        indent=2,
        default=str,
    )
    return run_structured(
        client,
        SYSTEM,
        (
            f"{catalogue_text()}\n\n"
            f"The deck:\n{deck}\n\n"
            "Illustrate the slides that draw nothing."
        ),
        toolset("visual").subset(["component_parameters", "component_build"]),
        Edit,
        max_iterations=max_iterations,
        max_tokens=6000,
        agent_name="visualizer",
    )


def undrawn_share(project: Project) -> float:
    """How much of the deck draws nothing: no component, or one that sets
    mathematics rather than a picture."""
    from proofmotion.components import COMPONENTS

    if not project.slides:
        return 0.0
    wordless = 0
    for slide in project.slides:
        if slide.code:
            continue  # hand-drawn scenes draw by definition
        spec = COMPONENTS.get(slide.component or "")
        if spec is None or not spec.pictorial:
            wordless += 1
    return wordless / len(project.slides)
