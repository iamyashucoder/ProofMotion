# Plan: a visual grammar

Written after seven sessions of adding components and one recurring verdict:

> "it is not about building com in lib. the job it tto serve as mathemtical
> solver using heavy vis and solving using the vis perspective"

Sixty-three components are registered. The last audit found nine had ever been
used. Every fix so far has read that as a coverage problem and answered with
more components. This document argues it is a *vocabulary* problem, and that
the answer is a smaller library with multiplicative reach rather than a larger
one with additive reach.


---

## 1. Why the catalogue cannot get there

A catalogue is a thing you search and miss. The searching was fixed (issue #9:
the whole catalogue is ranked, not substring-filtered). The missing was not,
because a miss has nowhere to go — it falls to the hand-drawn path, which
writes one scene from nothing with no tested geometry.

Three symptoms, one cause:

| Reported | What it really was |
|---|---|
| "Nothing in the catalogue fits" for a component that exists | the vocabulary is a list of nouns to match, not a question to answer |
| 13 steps, 14 slides, 0% drawing a figure | a sequence is a shape, and no component was that shape |
| Physics questions never used physics components | thirteen components nobody could name from a storyboard beat |

Adding a fourteenth shape does not close this. Adding a *grammar* does, because
a grammar has no miss: every idea is a sentence in it or the sentence is
malformed, and a malformed sentence is a diagnosable error rather than silence.

## 2. The one idea

Take the rule the visualizer agent already runs on, and make it a type instead
of a prompt:

> what varies here, and against what? Anything that varies is a function, and a
> function can be drawn.

Then everything drawable is a **Field**: a map from a domain to a codomain.

```python
Field(domain, codomain, sample, meta)
```

| What it is | domain | codomain |
|---|---|---|
| `y = f(x)` | interval | scalar |
| `z = f(x, y)` | grid | scalar |
| a vector field | grid | vector |
| a sequence, a series | discrete | scalar |
| a parametric curve | interval | ℝ² |
| a pipeline, a proof, a derivation | ordered index | label |
| a taxonomy, a comparison | categorical | label |
| a confusion matrix, a state space | categorical² | scalar |

The last three rows are the point. A flow diagram is a field over an ordered
index; a hierarchy is a field over a tree; a comparison is a field over
categories. They enter through the same door as a parabola. The cliff that
`§S8` proposed to fence off stops existing.

Prompt advice made structural is the move that worked before: composition was
a suggestion the coder ignored — 29% historically, 0 of the last 10 runs —
until the assembler made it deterministic and 603s became 113s. This is the
same move applied to selection.

## 3. Presentation — a table, not a decision

`(domain, codomain) → how it is drawn`. A lookup, reviewable at a glance. The
moment it needs logic, the grammar is wrong.

| domain \ codomain | scalar | vector | label |
|---|---|---|---|
| **discrete** | bars, stacked cells | arrows on nodes | flow, hierarchy, layers |
| **interval** | curve on axes | parametric curve | marked number line |
| **grid** | surface, heatmap | vector field | region map |
| **categorical** | table, matrix | — | comparison columns |

Empty cells are honest: there is no sensible vector field over a categorical
domain, and the table says so rather than a component failing at render time.
This is also the validity gate — it is what stops `partition(field)` from
emitting something confidently meaningless.

## 4. Verbs — written once, generic over `Field`

`trace` · `slide` · `partition` · `accumulate` · `morph` · `compare` · `map` ·
`zoom` · `project`

A verb never knows what it is animating. That is the whole economy:

| `accumulate` over… | reads as |
|---|---|
| an interval | a Riemann sum |
| ℕ | partial sums of a series |
| a categorical domain | a stacked bar |

One implementation, three components' worth of behaviour, and the third one
nobody would have thought to write.

## 5. Attachments — where "alive" lives

`label` · `readout` (live value) · `guide` (dashed drop-line) · `tangent` ·
`area` · `connector`

An attachment binds to a *point in the domain*, so when `slide` moves that
point the attachment follows. Issues #6 and #7 — figures static, nothing feels
alive — were fixed component by component. Here it is one mechanism, and
"maximum annotations" becomes a parameter rather than per-component work.

## 6. The arithmetic

```
today     63 components                         →  63 scene kinds     (additive)
grammar   12 presentations
        +  9 verbs
        +  6 attachments   = 27 implementations →  ~108 scene kinds   (multiplicative)
```

Adding a domain adds a row. Adding a verb applies to everything already there.
A catalogue can never have that property, and it is the only honest meaning of
"scalable" for this library.

## 7. Layout

```
proofmotion/vis/
  field.py       the Field type, domains, samplers
  present.py     the (domain, codomain) → presentation table
  verbs/         one file per verb, generic over Field
  attach/        annotations that bind to a domain point
  stage.py       frames, regions, clearing, continuity between slides
  score.py       beats, lag, run-time budget
  emit.py        a grammar term → ManimCE source
  golden/        one test per (presentation × verb) cell, generated
```

`emit.py` is deliberately thin. The assembler already turns a `ScenePlan` into
ManimCE source; grammar terms drop into the slot component names occupy today.
This is a new vocabulary, not a new renderer, and nothing downstream of the
selector changes.

## 8. What it does to the rest of the system

- **The selector's job collapses** from "which of 63 names?" to two questions:
  what is the field, and what happens to it. That is a question a model answers
  well, because it is the question a human explainer asks.
- **Learned components become safe by construction** — a learned component is a
  *named phrase*, a composition of verified primitives, rather than arbitrary
  code needing an admission gate.
- **Golden tests are generated** per cell, so coverage is structural instead of
  per-component effort.
- **The visualizer agent stops being advice** and becomes a grammar parse.

## 9. Where 3b1b's corpus fits, and where it must not

`3b1b/videos` is the best available evidence of which visual forms actually
explain things. It is also **CC BY-NC-SA 4.0** while this project is **MIT**,
and it is written against **ManimGL**, not the ManimCE 0.20.1 vendored here.

Both facts point the same way.

**Legitimate:** walk it offline and count which constructions recur, to rank
which cells of the presentation × verb grid to build first. A frequency table
is derived fact, not a derivative work. It replaces guesswork — `§S8` named
four shapes because one person guessed four; the corpus can say whether those
are the real four.

**Not legitimate, and not useful either:** copying scenes (ShareAlike would
relicense what it touched, NonCommercial contradicts MIT), or fine-tuning the
coder on it — that would teach ManimGL's API to a system that runs ManimCE,
making the coder worse at the library it actually uses.

The clone lives in a scratch directory. It is never vendored and never
committed. What lands in this repository is the table and our own components.

## 10. Migration — no big bang

1. **Spike.** `Field` + `present` + three verbs (`slide`, `accumulate`,
   `compare`). Measure with `eval/shape_coverage.py`.
2. **Port.** Existing components become named phrases, keeping their golden
   tests green. `function_plot` becomes `trace(Field(interval, scalar))`.
3. **Retire the catalogue as a vocabulary.** It survives as a phrasebook of
   common compositions, not as the thing the selector searches.

**Exit for step 1:** three verbs reach pictorial coverage at or above what the
63 components reach on the same twenty questions. If they do not, the catalogue
was right and this document is wrong — which is the cheapest possible outcome,
and the reason the spike comes before the port.

## 11. What not to build

- **More subject components.** Sixty-three exist; nine have been used. The gap
  was never coverage.
- **A better hand-drawn path.** Several sessions went into making it fail less.
  It should be reached rarely enough that its quality stops mattering.
- **A vendored copy of anything.** See §9.

## 12. Risks

- **Generic output can look flatter than a hand-tuned component**, and the
  first version will. Guard: presentations own aesthetics, verbs only
  choreograph — so a curve that looks wrong is fixed once for every curve.
- **The grammar becomes its own catalogue to miss.** Guard: cap the verbs. A
  new verb must cover a class of idea, never a topic.
- **The validity table is where complexity hides.** Guard: keep it literal. If
  it grows conditionals, the decomposition is wrong.
- **It is a real refactor of the selector's vocabulary.** Everything downstream
  survives; the selector's prompt and the component names do not.
