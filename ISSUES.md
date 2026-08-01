# Reported issues

Everything raised while using ProofMotion, in the order it was reported, with
what it turned out to be. Kept because the causes are more useful than the
symptoms: several reports that looked unrelated had one cause, and several
fixes that looked complete were not.

Status is `fixed`, `open`, or `partly` — and `partly` means the symptom is gone
and the cause is not.

---

## Quality of the output

| # | Reported | Cause | Status |
|---|---|---|---|
| 1 | Text overlaps curves in every scene | Layout was re-derived by the model per scene, never measured | fixed — regions, scored label placement, ink collision |
| 2 | Text unreadable over a filled shape | Ink was outline points only; a filled disc has none inside it, so a label across one measured perfectly clean | fixed — interiors sampled, `holds_text` for real containers |
| 3 | Steps unnecessarily long, text low quality | Scene length unbounded, no readability floor | fixed — budget per scene, font floor, measured |
| 4 | Axis numbers like `3300000.0` | Decimal places fixed regardless of magnitude | fixed — decimals follow the tick step, extremes become powers of ten |
| 5 | Text appears as LaTeX gibberish | The caption router asked "is this prose?" before "is this LaTeX?", so `x\text{-axis: ...}` went to a mobject with no LaTeX in it | fixed — a LaTeX command decides it first |
| 6 | Figures static, nothing feels alive | Two problems: 32 of 34 components had no motion, and every beat played `FadeIn` | fixed — components carry motions; reveals draw, write, and grow |
| 7 | None of the slides show motion | Same as 6, plus no motion components for the subject asked about | fixed — pendulum, spring, wave, field, ball, sums, network |
| 8 | Every slide restarts from a blank board | `read_from_previous` existed in the assembler and nothing ever set it | fixed — a run of slides carries its figure; slides carry a bridge phrase |

## What the system chooses to draw

| # | Reported | Cause | Status |
|---|---|---|---|
| 9 | Goes mostly for text, not diagrams | `component_search` was substring matching: "simple harmonic oscillator" returned nothing while `spring_mass` sat in the catalogue | fixed — the whole catalogue is returned, ranked not filtered |
| 10 | Physics questions never used physics components | Consequence of 9. Thirteen physics components had never been used in 71 runs | fixed — `inclined_plane` was chosen on the first run after |
| 11 | Asked for diagrams, got four equation slides | Assembly accepted a plan with zero components and skipped the coder | fixed — a plan must draw before it is assembled |
| 12 | Still no diagrams after that fix | The gate counted components, and `equation_chain` is a component that draws nothing | fixed — the gate counts pictures |
| 13 | 13 steps, 14 slides, 0% drawing a figure | Zero-figure plans warned and shipped anyway; the last slide described a pipeline by writing "arrow" between its stages | fixed — `flow_diagram`, and a plan that draws nothing has its shape drawn first |
| 14 | "Nothing in the catalogue fits" for a component that exists | An empty answer from one turn was read as a verdict on the library | fixed — an empty answer goes to the full pipeline first, hand-drawing last |
| 15 | Four requests for a neural network, four promises, no drawing | `needs_hand_drawn` was only read when the deck was empty | fixed — read on both paths |
| 16 | It is a maths solver using heavy visualisation, not a component library | The system searched the catalogue for subjects instead of asking what shape an idea has | **open** — `flow_diagram` covers sequences; comparison, hierarchy, layers, grid remain (PLAN-STUDIO-II §S8, §S9) |

## Speed

| # | Reported | Cause | Status |
|---|---|---|---|
| 17 | Twenty minutes per question | The whole conversation resent each turn — 79 calls × 6000 chars, quadratic | fixed — history compaction, 94% reduction |
| 18 | Still slow | Composition was advice in a prompt and mostly ignored, so the coder wrote every scene | fixed — deterministic assembler; 603s → 113s |
| 19 | Long waits show nothing | Progress events were on the bus and nothing emitted them | fixed — per-clip progress |
| 20 | Every change re-renders everything | The video was one Manim scene | fixed — per-run clips, content-hashed, joined by stream copy |

## Models and providers

| # | Reported | Cause | Status |
|---|---|---|---|
| 21 | Is deepseek-pro reasoning? We need it off | `DEEPSEEK_THINKING=0` only stopped us *requesting* thinking. Both v4 models reason when the key is absent | fixed — disabling is stated, not implied. Storyboard 119s → 37s |
| 22 | gpt-5.6 rejects `reasoning_effort` / tools | The 5.6 family refuses function tools on chat-completions | fixed — switches to `/v1/responses` and remembers per model |
| 23 | Support Ollama, test qwen3.6 and gemma4 | Both drive the agent loop correctly | **partly** — neither completes a run; structured output defeats them. Constrained decoding fixes it, verified, and needs a change to shared runtime |

## Crashes

| # | Reported | Cause | Status |
|---|---|---|---|
| 24 | `NoneType has no add_updater` | A helper with no `return`; the traceback blamed the wrong function | fixed — detected before render |
| 25 | `latex error converting to dvi` | Adjacent string literals joined without a space → `\quadK` | fixed — every literal typeset before render |
| 26 | `1 failed on s10`, unreadable message | Caption used `\cancel{m}`, which is not in Manim's preamble | fixed — cancel, mathtools, siunitx installed and added, only when present |
| 27 | `equation_chain: at least 2 items` | A scene with one equation was mapped onto a component that morphs between two | fixed — a lone equation is a caption |
| 28 | `unterminated string literal at line 21` | The coder's scene parsed; **the repair broke it**. A blanket replace of `\n` turned a two-line label's escape into a real newline | fixed |
| 29 | Same error again | The check ran as the operation was applied, too late for the coder to fix it | fixed — checked while the coder is still there, one retry |
| 30 | `TypeError: Failed to fetch` | Me, restarting the server underneath you. Three times | fixed by not doing it |

## The studio

| # | Reported | Cause | Status |
|---|---|---|---|
| 31 | One prompt to a finished video is too hard | Everything decided before anything is seen | fixed — a document, edited across turns |
| 32 | Connect the clips, do not start again | Rendering was whole-video | fixed — add a slide, render a slide |
| 33 | Needs a ChatGPT-like interface | — | fixed — chat, explorer, new chat, per-project transcript |
| 34 | An opening question returns one slide | The edit agent is small by design and was answering openings | fixed — an opening question runs the whole pipeline |
| 35 | Simple requests get the full treatment | `requires_derivation` was answered by the intent agent and never read | fixed |
| 36 | Remake appended instead of replacing | `draw_by_hand` always emitted `add` | fixed |
| 37 | Remaking pi on slide 4 appended nine Monte Carlo slides | Escalating from a remake lost the slide it named | fixed — declines and says where to ask |
| 38 | Launch starts at s14, not s1 | It resumed the most recent project | fixed — opens a new one, explorer keeps the rest |
| 39 | Slides should be primary, video secondary | It was a video player | fixed — deck first, filmstrip, arrow keys, video one click away |
| 40 | Can Canva go in here? | — | won't do — it is someone else's product and knows nothing about these components. Direct manipulation exists: drag the figure, title or caption on the slide |
| 41 | Chat and video collide | Five stacked regions each choosing its own height, a poster measured against the viewport | fixed — explicit grid rows, foldable settings |
| 42 | Nothing like a chat studio | Every recent question fell to the weakest path, and I was making that path fail less rather than not reaching it | **partly** — 14 fixed the routing, 16 is the real answer |
| 43 | Narration written for every scene, spoken nowhere | — | fixed — piper per slide, cached by content, mixed into the join; the `speak` pill plays one slide |
| 44 | A narrated render hangs until ffmpeg is killed | Bare `apad` pads without end and `-shortest` stops at the shortest *input* — a filtergraph output is not an input, so nothing ended the encode. Thirteen slides died at the 300s timeout | fixed — the pad is bounded by the film's measured length; the same mix now takes 0.6s |

---

## Still open

1. **Shapes, not subjects** (16). Four more shape components and a selection step
   that asks what shape an idea has. This is the one that changes the experience.
2. **Ollama cannot finish a run** (23). Constrained decoding, verified to work,
   needs a change to shared runtime.
3. **The deck is not a document yet** (39). Reorder by dragging, duplicate, edit
   a title in place — the operations exist and have no handle.
4. **Export.** No PDF, no way to take a deck elsewhere.

## Things I got wrong, kept deliberately

- Told you extended thinking cost 25 minutes and bought nothing. That compared
  high effort against *omitted*, and omitted was still reasoning. It measured
  two reasoning configurations, not reasoning against none.
- Claimed a follow-up re-rendered every clip. It had not; I read a mid-flight
  number.
- Said the repository had moved when the push failed. It had not — the active
  `gh` account had no access, and GitHub reports that as "not found".
- Pushed three commits with failing tests. Same cause each time: piping pytest
  into `tail` makes the exit status `tail`'s, so `&&` never saw the failure.
- Spent several turns making the hand-drawn path fail less, after you had twice
  said the problem was not the component library.
