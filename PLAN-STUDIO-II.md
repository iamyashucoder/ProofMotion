# Plan: the studio, reviewed

Written after a long session of fixing the studio one report at a time. Most of
those fixes were real and the whole still does not feel like a studio, which is
the signal that the problems were not where I was looking.

This is a review of what the pipeline actually does, what goes wrong in it, and
what to build — in the order that changes the experience most.

---

## 1. What the pipeline does now

```
message
  │
  ├─ deck empty ──▶ understand ──▶ requires_derivation?
  │                                   │
  │                        yes ──▶ plan ▶ verify ▶ storyboard ▶ components
  │                                   │
  │                        no  ──▶ propose (edit agent, catalogue)
  │                                   │
  │                        empty ──▶ full pipeline ──▶ hand-drawn
  │
  └─ deck exists ─▶ propose ─▶ operations ─▶ apply ─▶ render changed units ─▶ join
```

Rendering is the part that works. A run of slides sharing a figure is one clip,
keyed by content; editing one re-renders one; joining is a stream copy. Adding a
slide costs a slide. That design holds and nothing below asks to change it.

## 2. What actually goes wrong

Seven sessions of reports, grouped by cause rather than by symptom.

**The answer arrives as prose that describes a picture.** Thirteen correct steps
about post-training went out as fourteen slides of text, the last of which wrote
"arrow" between the stages of a pipeline. The plan is a sequence; the deck
should have drawn it. `flow_diagram` and the fallback that draws a plan's shape
close this for sequences, and only for sequences.

**The catalogue is searched, not thought with.** The agent asks "is there a
component for this?" and a miss ends the conversation. It never asks "what is
the shape of this idea?" — which is the question that finds `flow_diagram` for a
process, a comparison for a trade-off, a hierarchy for a taxonomy.

**Failure falls to the weakest path.** Any empty answer used to go straight to
hand-drawing, which writes one scene from nothing with no tested geometry. That
is now the last resort rather than the first, but it is still where anything
outside the catalogue lands, and it still produces thin slides.

**The tools fought the content.** Captions in the caption strip, a bridge over
the equation it introduced, a poster that was the closing fade. Each was a
layout decision made in isolation from what else was on screen.

**The interface was a video player.** Reading slide seven meant scrubbing. Fixed
by making the deck primary; the remaining gap is editing.

## 3. What to build

Ordered by how much each changes the experience, not by size.

### S8 — Shapes, not subjects

`flow_diagram` was worth more than every ML component would have been, because
a process, a derivation, a proof and a pipeline are one shape. Four more cover
most of what an explanation ever needs:

| Shape | Reads as | Answers |
|---|---|---|
| `comparison` | two columns, aligned rows | this versus that, before and after, trade-offs |
| `hierarchy` | a tree | taxonomies, decompositions, call structure |
| `layers` | stacked bands | architectures, abstraction levels, protocol stacks |
| `grid_map` | labelled cells | matrices, tables, confusion matrices, state spaces |

Each takes labels and structure, nothing domain-specific, and each carries a
motion: the comparison reveals row by row, the hierarchy grows from its root,
the layers stack, the grid fills.

**Exit:** a question with no matching subject component still produces a figure,
because its *shape* is in the library.

### S9 — Ask for the shape

The selection prompt asks which component fits. It should ask what shape the
idea has, and only then which component draws that shape. A miss then falls to a
shape rather than to a blank.

**Exit:** pictorial coverage above 0.8 on a mixed set of twenty questions, with
no subject-specific component added.

### S10 — The deck as a document

The operations exist and have no handle: reorder, duplicate, edit a title.

- drag a thumbnail to reorder — `reorder`, re-renders nothing
- duplicate a slide — `add` with the same parameters, one render
- edit a title or caption in place — `edit`, one render
- a slide's own notes, shown under it and spoken later

**Exit:** a deck can be rearranged and retitled without going through the chat.

### S11 — Export

A deck that cannot leave is a demo. PDF of the posters, the mp4, and the
document itself so a project can be reopened elsewhere.

### S12 — Speak it

Narration is already written for every scene and rendered nowhere. Text to
speech per slide, timed to the clip, mixed into the join. This is the difference
between a deck and a video someone can watch without the person who made it.

## 4. What not to build

**More subject components.** Fifty-four exist and nine have ever been used. The
gap is not coverage, it is that a miss has nowhere to go — which S8 and S9 fix
for every subject at once.

**A better hand-drawn path.** Several turns went into making it fail less. It
should be reached rarely enough that its quality stops mattering.

**Embedding Canva.** It is someone else's product and it knows nothing about
these components. Direct manipulation of what the components produce is the part
that was worth having, and it exists.

## 5. Risks

- **The shape components could become their own catalogue to miss.** Guard: five
  at most, each covering a class of idea rather than a topic.
- **Slide-level editing invites drift** between what the document says and what
  the person sees. Guard: every edit stays an operation; the poster is derived,
  never authoritative.
- **Narration doubles render time.** Guard: it is generated per slide and cached
  by content, like everything else.
