# Plan: composition over codegen

> The model decides what a visualization *means*. Python decides where things go.
>
> Supersedes PLAN.md Phase 4 and pulls Phases 5–6 forward.

---

## 1. Diagnosis

Text keeps landing on curves. The reason is structural, not a matter of prompt
quality.

**What exists today**

| Check | Runs when | Catches |
|---|---|---|
| `layout_check` | storyboard planning | overlaps between *hypothetical* boxes |
| `inspect_scene` | after code is written | text-over-**text**, off-frame, tiny text |

**What is missing:** text over *ink* — curves, axes, arrows, shapes. I excluded
text-vs-shape from `inspect_scene` deliberately, because a label inside a box or
a tick number beside its axis is intentional, and a checker that flags those gets
ignored. The result is that the single most visible defect is the one nothing
looks for.

**It is precisely detectable.** A probe over existing scenes, testing whether any
sampled point of a non-text `VMobject` falls inside a text bounding box:

```
20260725T122834Z  text-on-ink collisions: 5
   MathTex(x_{t+1}=x_t-\eta f'(x_t))  sits on  NumberLine     <- the real defect
   MathTex(f(x))                      sits on  VMobjectFromSVGPath
   DecimalNumber                      sits on  NumberLine     <- false positive
```

Exactly the collision visible in that scene's rendered frame. Two false-positive
classes appeared and both have clean rules:

- **Glyph paths.** `VMobjectFromSVGPath` is a text's own outline. Ink belonging to
  any text unit must be excluded from the ink set.
- **Designed attachments.** A `DecimalNumber` tick label sits on its own
  `NumberLine` by construction. Rule: only flag when the text and the ink belong
  to *different* mobject trees.

Detection is therefore solved in principle. But detection is not the goal —
**prevention** is, and prevention means the model should not be placing objects
by hand at all.

---

## 2. The principle

> The language model should not write low-level Manim layout code when a
> verified deterministic tool or reusable template can do the job.

| Owner | Responsibility |
|---|---|
| **Model** | mathematical meaning, pedagogical sequence, visual intent, tool choice, tool parameters |
| **Python** | calculation, layout, text fitting, object construction, overlap prevention, rendering, validation |

Codegen becomes the **fallback**, not the default. Today it is the only path,
which is why every scene re-derives axis placement, label offsets, and font sizes
from scratch — and gets them wrong in a new way each time.

---

## 3. Layer 1 — Deterministic layout engine

Three pieces, each independently testable and usable without an LLM.

### 3.1 Regions

A scene declares a layout, not coordinates. Regions are computed from the frame
and never overlap by construction.

```python
class Region(BaseModel):
    name: str                  # "title" | "stage" | "sidebar" | "caption"
    left: float; right: float
    bottom: float; top: float

LAYOUTS = {
    "title_stage_caption": ...,   # title bar, large stage, caption strip
    "stage_sidebar":       ...,   # plot left, equations right
    "split":               ...,   # two equal stages
    "full":                ...,
}
```

`place(mobject, region, align="center", fit=True)` scales-to-fit and positions.
A title cannot collide with a caption because they occupy disjoint rectangles.
This alone removes the majority of observed defects, including every
"old title still on screen under the new one" case, since a region holds one
occupant at a time and `place` evicts the previous one.

### 3.2 Label placement

For labels that must attach to a point on a curve, regions are not enough. This
is the map-labeling problem and it has a standard solution: score candidate
positions, take the best.

```python
def place_label(label, anchor, avoid, *, distances=(0.25, 0.45, 0.7)) -> Mobject:
    """Position `label` near `anchor` in the position that collides least.

    Candidates: 8 compass directions x several distances. Each is scored on
    ink overlap, overlap with already-placed labels, distance from the anchor,
    and frame violation. Lowest score wins; if every candidate collides, the
    label goes to free space with a leader line.
    """
```

Leader lines matter: when a curve genuinely fills the region, a good figure moves
the label out and connects it. Manim will never do that on its own.

### 3.3 Ink collision check

`inspect_scene` gains text-over-ink using the probe above, with the two exclusion
rules. It reports the offending pair and the free space nearest the anchor, so a
fix is mechanical.

**Exit:** the four scenes rendered so far are re-checked; every collision visible
in their frames is reported, and no tick label or in-box label is.

---

## 4. Layer 2 — The component library

Parameterized, tested, versioned builders. Each returns a `VGroup` plus layout
metadata, uses the layout engine internally, and is verified to produce no
overlaps across its parameter range.

```python
@component(version=1, domain="calculus")
def function_plot(
    expr: str, x_range: tuple[float, float], *,
    y_range: tuple[float, float] | None = None,   # inferred by numeric_sample
    label: str | None = None,
    marks: list[PointMark] = (),
) -> Built:
    """A function graph with axes, sensible ranges, and non-colliding labels."""
```

Starting set, chosen because they cover what has actually been requested:

| Component | Covers |
|---|---|
| `function_plot` | any single-variable graph |
| `tangent_secant` | derivatives, limits of secants |
| `riemann_area` | integration, accumulation |
| `iteration_trace` | gradient descent, Newton, fixed points |
| `unit_circle` | trigonometry |
| `labeled_polygon` | triangle/angle geometry |
| `number_line_marks` | sequences, intervals, inequalities |
| `grid_of_cells` | arrays, algorithms, counting arguments |
| `vector_field` | ODEs, physics |
| `matrix_transform` | linear algebra |
| `equation_chain` | any rewrite sequence (`TransformMatchingTex`) |

Every component ships with:
- a Pydantic parameter model, so the tool schema is generated, not written
- golden tests: build across the parameter range, run `inspect_scene`, assert clean
- a version, so improving one does not silently change old projects

**Exit:** a component covers a request end-to-end with the model supplying only
parameters, and its golden tests prove no overlap at the parameter extremes.

---

## 5. Layer 3 — Composition-first generation

The coding agent's job changes from "write a scene" to "choose components and
parameters, and only write code where nothing fits".

```
storyboard beat
      |
      +-- component_search(intent)     which components could express this?
      |
      +-- fits?  --> component_build(name, params)   deterministic, verified
      |
      +-- no fit --> write_manim_code(...)           fallback, flagged in state
```

`state.composition` records, per beat, whether a component or the fallback was
used. That number is the health metric for the whole effort: fallback share
should fall over time, and every fallback is a candidate for Layer 4.

**Exit:** on a representative prompt set, a majority of beats are built from
components, and component-built beats have zero layout defects.

### 5.1 Why this became an assembler — measured, 2026-07-26

As written above, composition was advice in the coder's prompt, and the numbers
said advice was not enough: 29% of runs across the whole history, and none of
the last ten. A model asked to prefer components will sometimes prefer them.

So the decision moved out of the prompt. The model still chooses *which*
component expresses a scene and with what parameters — that is judgement, and it
is good at it. Everything after that is emitted by `proofmotion/compose`:

```
storyboard --> plan_from_storyboard()   the director already named components
                     |                   -> derived, no model call at all
                     +-- can't read it?
                     |
               select_components()      one structured call, verified by
                     |                  component_build before it commits
               assemble()               emits the scene: placement, reveal
                     |                  order, and clearing the stage
               coder loop               only when neither path produced a plan
```

Rules that used to be prose the coder could ignore — clear the stage between
sections, place titles in regions, keep text above the readable floor — are now
emitted code, held by tests rather than by hope.

A scene with no component is still assembled, as a titled equation slide. The
first version refused any plan with a gap, and a single algebra scene among four
sent the whole run down the slow path.

Measured on one prompt, deepseek-v4-flash, identical question:

| | before | selector | derived |
|---|---|---|---|
| wall clock | 603s | 398s | 115s |
| prompt tokens | 396k | 264k | 122k |
| API calls | 50 | 42 | 20 |
| composed | no | yes | yes |
| coder turns | 39 | 0 | 0 |

The remaining time is the director: 69s of the 115s. That is now the bottleneck,
and it is doing component search work the assembler could consume directly.

### 5.2 The director, and what did not work

The director held the layout tools and spent nine of twenty-two calls measuring
hypothetical text boxes — placement it no longer owns, since the assembler
places everything and components own their internals. Removing them was clearly
right on principle. **It did not make the stage faster.**

| | run 3 | run 4 | run 5 (layout tools removed) |
|---|---|---|---|
| storyboard | 69.3s | 119.0s | 100.3s |
| director calls | — | 22 | 21 |
| layout calls | — | 9 | 0 |

Run-to-run variance on an identical prompt swamps the change, and the freed
calls were simply spent elsewhere: `typeset_check` went 5 → 10, `component_build`
3 → 6. Nine turns before, nine turns after.

**Turns are the cost, not tools.** Each turn emitted 1,500–2,700 output tokens
and took 12–22 seconds; output tokens are the wall clock. Cutting a stage means
cutting round trips or cutting what the model must write, not trimming its
toolbox. The remaining candidates are the unread fields in the storyboard schema
(`narration` is the largest, and is a human-editing surface rather than dead
weight) and merging the director into the selection step entirely.

### 5.3 The regression this surfaced

Told to express every scene as one component, the director returned four scenes
naming the *identical* component with *identical* parameters. The assembler tore
the figure down and rebuilt it between each, so the viewer watched the same
parabola fade out and back in four times — every scene individually correct.

The assembler now clears the words and the picture on different schedules. The
title and caption change every scene; the figure is replaced only when it
actually differs. A run of scenes about one figure keeps it on screen and lets
the words change around it, which is what an explanation staying with a diagram
should look like anyway.

---

## 6. Layer 4 — Harvesting one-offs into components

Every successful fallback is a component that does not exist yet.

After a run that rendered cleanly, a harvester agent examines the fallback code
and proposes:

1. a parameterized signature, generalizing the constants it found
2. a docstring stating when to use it
3. golden tests at the parameter extremes
4. a domain tag and version

The proposal lands in `components/pending/` and enters the registry only after
review — consistent with the human-approved registry decision in PLAN.md §6.
Generated components execute like any other code, so approval is the control.

**Guard against a library of near-duplicates:** before proposing, the harvester
must run `component_search` and justify why nothing existing fits. A proposal
that overlaps an existing component becomes a *parameter* on that component
instead, and bumps its version.

**Exit:** a one-off from a real run becomes an approved component, and a later
request on a related topic composes it without writing code.

---

## 7. Layer 5 — Interactive HTML output

Components are parameterized and deterministic, which is exactly what makes an
interactive export possible: the parameters are already declared, so the sliders
write themselves.

```
component + ParamSpec[]  --+--> Manim  --> MP4        (export)
                           |
                           +--> HTML   --> canvas + sliders   (interactive)
```

Each component optionally implements `to_html()`, emitting a **self-contained**
page: geometry as JSON, a small vanilla-JS renderer, KaTeX for the maths (same
LaTeX string as the Manim path), and one control per parameter.

Which parameters are live follows the classification already designed in
PLAN.md §4: `client` for values that only feed precomputed geometry (a point
moving along a curve, a highlighted interval), `server` for anything changing
topology.

And the payoff that makes this more than a slider: **`valid_domain` from the
proof.** Drag a learning rate past `2/L` and the iterates diverge — the UI shades
the invalid region and the caption explains which hypothesis broke. That is the
thing a chart library cannot do.

Scope honestly: start with the graph family (`function_plot`, `tangent_secant`,
`riemann_area`, `iteration_trace`), which are parameter-friendly and cover most
requests. Geometry and matrix components come later.

**Exit:** one component exports an HTML page whose slider changes the figure at
60fps, matching its MP4 at the default parameter values.

---

## 8. Phases

| Phase | Work | Exit criterion |
|---|---|---|
| **T1** | Ink-collision detection + the two exclusion rules | Every collision visible in existing frames reported; no tick/in-box false positives |
| **T2** | Region layout engine + `place()` | A scene built only from regions cannot overlap; old content evicted automatically |
| **T3** | `place_label` with candidate scoring and leader lines | Labels on a dense curve place without collision across a parameter sweep |
| **T4** | First four components + golden tests | Each builds clean across its parameter range |
| **T5** | Composition-first coder; `state.composition` | Majority of beats component-built; those beats defect-free |
| **T6** | Remaining components | Coverage across calculus, geometry, linear algebra, algorithms |
| **T7** | Harvester + pending registry + approval CLI | A real one-off becomes an approved component and is reused |
| **T8** | HTML export for the graph family | Slider-driven page matching the MP4 |

T1–T3 are the quality fix and should land first; they help even before any
component exists, because the fallback path uses them too.

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Components become a straitjacket, refusing unusual requests | The fallback never goes away. Fallback share is a metric, not a failure. |
| Harvested library fills with near-duplicates | `component_search` justification required before proposal; overlapping proposals become parameters plus a version bump. |
| HTML renderer diverges from Manim output | Both consume the same component parameters; a visual-diff test at default parameters is the T8 gate. |
| Label placement is slow on dense scenes | Candidates scored against a coarse occupancy grid, not full geometry; cache per beat. |
| Versioning churn breaks old projects | Projects record the component version they used; builders keep old behaviour behind the version tag. |

---

## 10. What this changes about the current system

- `agents/coder.py` stops being the primary path and becomes the fallback.
- `inspect_scene` becomes the acceptance gate for components, not just a repair signal.
- The `visual` toolset gains `component_search`, `component_build`, `place_label`.
- `prompts.py` is already gone; this removes the *need* for its replacement, since
  layout rules become code with tests rather than instructions with hope.
