# Plan: the studio

One prompt to a finished video is the hardest version of the problem and the
one with the worst feedback loop. Everything is decided before anything is
seen, a defect anywhere means starting over, and the person who knows what the
explanation should look like — the one reading it — cannot touch it.

This plan turns the pipeline inside out. Not "generate a video" but "keep a
document, and project a video from it". One-shot stays: it becomes the case
where the document is filled in a single turn.

---

## 1. The reframing

Today the pipeline is a function.

```
prompt ──▶ [ understand · plan · verify · storyboard · assemble · render ] ──▶ video
```

Everything is transient. `create_math_animation` returns a state object, writes
an mp4, and the next question starts from nothing. A follow-up cannot extend
the video because there is nothing to extend — only code to re-run.

The studio makes the document durable and the video derived.

```
project.json ──assemble──▶ per-slide code ──render──▶ clips ──concat──▶ video
     ▲                                                    │
     └──────── operations (from a person, or an agent) ────┘
```

The document is the artifact. The video is a projection of it, rebuilt from
whatever changed. Asking a follow-up question appends to the document; nothing
already rendered is touched.

**This is why "extend, not repair" needs per-slide rendering.** Repair exists
because the whole video is one Manim scene: change anything and everything must
be re-derived. Once slides render independently, adding one costs one slide.

---

## 2. What already exists

Most of the pieces are built. This is a reorganisation more than a new system.

| Needed | Already have |
|---|---|
| A scene document | `ScenePlan` / `SceneAssignment` — ordered, typed, validated |
| Document → code | `proofmotion/compose/assemble()`, deterministic |
| Typed parameters per figure | Every component carries a Pydantic model |
| Parameter metadata for controls | `model_json_schema()`, with bounds and defaults |
| Placement primitives | `layout/regions.py`, `place()`, named regions |
| Defect measurement | `inspect_scene`, `text_on_ink`, fill detection |
| A web surface | `tools/preview_server.py`, `proofmotion/web/live.py` |
| Per-project persistence | `generated_projects/<id>/` with state and storyboard |

What is missing is durability, incrementality, an edit vocabulary, and a
surface that exposes the parameters that already exist.

---

## 3. The document

`project.json` becomes the source of truth. It is `ScenePlan` plus identity and
history.

```jsonc
{
  "project_id": "20260728T...-a1b2",
  "question": "Show how the area under x^2 is built from Riemann rectangles",
  "revision": 7,
  "slides": [
    {
      "id": "s1",                    // stable across edits; the render cache key
      "title": "Area under the curve",
      "component": "function_plot",
      "parameters": {"expr": "x**2", "x_min": 0, "x_max": 3},
      "caption": "f(x)=x^2",
      "seconds": 6.0,
      "overrides": {},               // §7
      "origin": "agent",             // or "human"
      "locked": false                // a slide the person is happy with
    }
  ]
}
```

Slide `id` is stable. Reordering moves entries; it does not renumber them, so a
reordered video re-renders nothing.

`locked` is the promise that makes a studio usable: an agent may not silently
rewrite a slide the person has settled. It may propose, and the proposal
surfaces as a suggestion rather than an edit.

---

## 4. Per-slide rendering, and the cache

Each slide is emitted as its own `Scene` subclass and rendered to its own clip.
The final video is the concatenation.

The cache key is a content hash over everything that can change the pixels:

```
hash(component, parameters, title, caption, seconds, overrides, component.version)
```

`component.version` matters. A component improved in the library must
invalidate clips built from the old one, or an edited project silently mixes
two generations of the same figure.

Edit slide 4 of nine: one clip re-renders, eight are reused, ffmpeg concatenates.

**The honest cost.** The assembler currently holds an unchanged figure on
screen across consecutive scenes — built deliberately, because rebuilding an
identical parabola four times made the viewer watch it flicker. Independent
clips break that: the held figure becomes a hard cut at every slide boundary.

The fix is to render *runs* rather than slides. Consecutive slides sharing the
same component and parameters form one render unit, cached as a unit. Editing
the caption of slide 5 in a run of 5–7 re-renders that run, not the video. This
is the one place where the design cannot be naive, and it should be built this
way from the start rather than retrofitted.

Concat also demands identical codec settings across clips, so render settings
are fixed at the project level rather than per invocation.

---

## 5. The edit vocabulary

Every change — human or agent — is an operation on the document. Not a
regenerated plan: a diff.

```python
add_slide(after: str | None, slide: Slide)
edit_slide(id: str, **fields)
set_parameter(id: str, name: str, value: Any)
reorder(id: str, before: str | None)
delete_slide(id: str)
set_lock(id: str, locked: bool)
```

Pure functions over the document, independently testable with no model in the
loop, exactly as `assemble()` is now.

This is also what makes multi-turn tractable for the model. Answering "now show
what happens as n grows" means emitting two `add_slide` operations, not
restating an eighteen-scene storyboard. Small structured output is more
reliable output — and it is the difference between a 36B local model succeeding
and running out of budget mid-JSON, which is exactly where qwen3.6 failed.

**One-shot is not a separate path.** It is an agent emitting N `add_slide`
operations in one turn against an empty document. Same code, same cache, same
checks.

---

## 6. Parameter controls, for free

Every component already declares its parameters as a Pydantic model with types,
defaults and bounds. A control panel derives from that with no per-component
work:

| Field | Control |
|---|---|
| `float` with `ge`/`le` | slider over the declared range |
| `int` with bounds | stepper |
| `Literal[...]` | dropdown of exactly the valid options |
| `bool` | checkbox |
| `str` | text field |
| `list[str]` | editable list |

`riemann_area(rectangles=6)` becomes a slider the person drags from 3 to 24 and
watches the estimate converge. That is the thing this system should have been
able to do all along, and it needs no new metadata — only a surface.

Validation is already enforced by the model, so a control cannot produce a
value the component rejects. Invalid combinations that only the component knows
about — `distribution_plot` with an exponential rate of zero — are already
caught by its validator and surface as a message rather than a crash.

---

## 7. Fixing layout by hand

The reason a person needs this: a checker can measure overlap, and it cannot
know that a label reads better slightly left. The layout engine already places;
the studio adds an override layer applied after placement.

```jsonc
"overrides": {
  "labels": {"caption": {"dx": -0.4, "dy": 0.1}},
  "font_sizes": {"title": 36},
  "region": "stage_sidebar"
}
```

Applied deterministically by the assembler after `place()`, so an override is
part of the document, survives re-render, and is diffable.

Crucially the checker still runs. Dragging a label reports whether the overlap
is now clear — the person edits, and the measurement tells them whether it
worked. That is the loop `inspect_scene` was built for and has never had a
human on the other end of.

---

## 8. Phases

Each phase is independently useful and independently testable. No phase depends
on the UI existing.

**S1 — the document.** `project.json` as source of truth; load, save, validate,
revision. Assemble from it. Render whole, as today. Exit: a project round-trips
through disk and produces the same video.

**S2 — runs, clips and the cache.** Group consecutive slides into render units,
emit one Scene per unit, content-hash, render, concat. Exit: editing one slide
of nine re-renders one unit, and the video is byte-identical elsewhere.

**S3 — operations.** The vocabulary above as pure functions, plus an agent that
proposes operations from a follow-up message against the current document.
Exit: "now add a scene showing 24 rectangles" appends without touching slides
1–8.

**S4 — controls.** Derive control specs from component schemas; serve them;
apply a change; re-render the affected unit. Exit: dragging `rectangles` from 6
to 24 updates the video without a model call.

**S5 — overrides.** Nudges, font sizes, region choice; checker re-runs and
reports before and after. Exit: a person can fix an overlap the polisher could
not.

**S6 — the studio surface.** Built on `tools/preview_server.py`: filmstrip of
slides, parameter panel, override handles, a box for the next question, and the
event stream already feeding the live view.

**S7 — one-shot parity.** The single-prompt path expressed as operations, so
both routes share the cache, the checks and the document.

---

## 9. What this fixes that is currently broken

- **Repair is measurement-blind.** The repair path re-renders without re-running
  layout, typeset or validation, so a repaired scene ships unmeasured — which is
  how the Riemann video shipped with overprinted captions while the report said
  zero overlaps. Per-unit rendering removes most of the need for repair, and
  every unit passes the same gates before it is cached.
- **Nothing is reusable.** Seventy-five runs have produced seventy-five
  throwaway scenes. A document can be forked, edited and re-rendered.
- **The person cannot help.** Every defect today is the system's to find. Most
  of them a human could fix in seconds if there were anywhere to click.

## 10. Risks

- **Seams between clips.** Fixed render settings and identical codecs, verified
  by a test that concatenates and checks frame continuity.
- **Continuity across a run boundary.** Addressed by run grouping (§4); it is
  the design's sharpest constraint and the reason the cache is per-run.
- **Document drift.** Components evolve; a project pinned to old parameters may
  no longer validate. Validate on load and report, never silently coerce.
- **Scope.** S6 is a real front end. S1–S5 are useful without it and testable
  from the CLI, which is the order they are listed in.
