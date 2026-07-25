# ProofMotion — Architecture & Phased Build Plan

> Verified mathematics, animated. An AlphaProof-style neuro-symbolic proof engine
> feeds a deterministic scene compiler, rendered live in the browser and exported
> through Manim.

---

## 0. Decisions locked

| Question | Decision | Rationale |
|---|---|---|
| Live rendering | **Option C** — Manim computes geometry, browser draws it | Reuses Manim's math; browser is a viewport, not a reimplementation |
| LLM backend | **Provider-agnostic over OpenRouter** | Extends existing `llm/base_client.py` Protocol into a real provider layer |
| Outer orchestration | **Hand-rolled typed runtime** | ~8 nodes + one retry loop over the existing `MathAnimationState`. Framework weight not justified |
| Proof search | **Purpose-built kernel** | This is the core IP. It is a search algorithm, not an agent conversation |
| Verification | **Tiered, domain-routed**: SymPy+numeric → Z3 → DDAR → Lean | No single engine spans "basic to advanced" |
| Codegen | **SceneSpec IR + deterministic compiler** | The LLM emits validated data, not Python |
| Sandbox | **Largely dissolved by the IR** (see §6) | Remaining exec risk is agent-authored tools only → human-approved registry |
| Math typesetting | **LaTeX canonical, Typst fast path, KaTeX in browser** | One source string, three renderers |

---

## 1. The MAS question, answered

**The premise needs correcting: AlphaProof and AlphaGeometry 2 are not multi-agent
systems in the framework sense.** They are search algorithms with a neural policy
and a deterministic oracle. Choosing CrewAI or AutoGen for this is a category
error — those model agents *conversing*, and a proof search has no conversation
in it. What it has is a frontier, an expansion function, a verifier, and
backtracking.

Evaluated and rejected as the core:

| Framework | Why not |
|---|---|
| **CrewAI** | Role-playing crews, sequential/hierarchical only. No search, no backtracking. |
| **AutoGen / AG2** | Group-chat driven; strength is emergent dialogue. Wrong abstraction, heavy. |
| **OpenAI Agents SDK / Swarm** | Handoff-based, conversational, OpenAI-centric. No checkpointing. |
| **LlamaIndex Workflows** | Event-driven and decent (and already in the env), but its value-add over hand-rolled here is thin, and it drags in the LlamaIndex ecosystem. |
| **LangGraph** | Genuinely good for the *outer* pipeline — conditional edges match the render-success/fail branch, checkpointers and interrupts match storyboard approval. But it models **bounded** state machines, and unbounded tree search with a shared frontier fights it at every turn. |
| **Claude Agent SDK** | Ruled out by the provider-agnostic decision. |

**Final architecture — split the decision by layer:**

1. **Outer pipeline** → hand-rolled typed runtime. Steal exactly one idea from
   LangGraph: a `Checkpointer` protocol, so a 20-minute proof search survives a
   crash. Nothing else earns its dependency weight for eight nodes.
2. **Inner proof search** → purpose-built kernel (~400 lines). Every serious
   system in this space — AlphaProof, AG2, DeepSeek-Prover, LeanDojo-based
   provers — hand-rolls this, because there is no framework for it. The
   abstraction is a search algorithm.
3. **DSPy** → optional, later, for the Formalizer only. "NL → formal statement
   that compiles" is a verifiable metric, which is precisely DSPy's sweet spot.
   A component, not the framework.

The two tricks worth lifting from AG2 specifically:
- **Auxiliary-construction proposal** — the LLM's only job is adding one object,
  never asserting a proof.
- **Shared fact store across parallel search trees** (SKEST) — cheap to
  implement, large speedup.

---

## 2. Architecture

```
                          User question
                                │
                    ┌───────────▼───────────┐
                    │   Orchestrator        │  hand-rolled typed runtime
                    └───────────┬───────────┘  + Checkpointer
                                │
                    Intent & Scope Agent ──────► ParamSpec[]  (free parameters
                                │                              in the question)
                    Mathematical Planner
                                │
                    Formalizer Agent ─────► {SymPy | Z3 | DDAR | Lean}
                                │
        ┌───────────────────────▼────────────────────────┐
        │            PROOF SEARCH KERNEL                 │
        │  frontier (best-first)                         │
        │  LLM policy proposes step / aux construction   │◄── shared fact store
        │  verifier oracle accepts / rejects             │    (SKEST)
        │  subgoal decomposition on failure (DSP)        │
        │  checkpointed                                  │
        └───────────────────────┬────────────────────────┘
                                │
                          ProofDAG  ◄── certified; carries hypotheses
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
   Math Reviewer         Pedagogy Agent         Visual Director
         └──────────────────────┼──────────────────────┘
                                │
                        SceneSpec (IR)  ◄── ParamSpec bound to ValueTrackers
                                │
                    ┌───────────┴───────────┐
                    ▼                       ▼
        Deterministic compiler      Geometry serializer
                    │                       │
              Manim scene           flat scene graph (JSON)
                    │                       │
              MP4 export            WebGL runtime (live, 60fps)
                    │                       │
            Visual Reviewer ◄────────────────┘
                    │
              Debug Agent (on failure) ──► back to SceneSpec
```

**The load-bearing idea:** the ProofDAG *is* the storyboard. Topologically
sorted, node depth becomes pacing, dependency edges become visual callbacks to
earlier results, and the verification tier tells the Visual Director how much to
assert versus hedge. This replaces the hardcoded `if/elif` chains in
`agents/math_planner.py` entirely.

---

## 3. Core contracts

These three schemas are the whole system. Everything else is an implementation
of a transform between them.

### ProofDAG — output of the proof kernel

```python
class ProofNode(BaseModel):
    id: str
    statement_latex: str
    kind: Literal["given", "definition", "deduction", "construction", "goal"]
    justification: str              # human-granularity, animatable
    rule: str | None                # formal rule name, if any
    depends_on: list[str]
    verified_by: Literal["sympy", "numeric", "z3", "ddar", "lean", "assumed"]
    certificate: dict               # engine-specific proof object
    hypotheses: list[str]           # constraints that must hold, e.g. "0 < eta < 2/L"
    visual_hint: dict | None

class ProofDAG(BaseModel):
    problem_nl: str
    formal_statement: str
    nodes: list[ProofNode]
    goal_id: str
    params: list[ParamSpec]
```

### ParamSpec — the interactivity contract

```python
class ParamSpec(BaseModel):
    name: str                       # "eta"
    latex: str                      # r"\eta"
    kind: Literal["real", "int", "bool", "choice", "point"]
    default: float | int | bool | str
    domain: tuple[float, float] | list[str]     # UI range
    valid_domain: str | None        # sympy predicate inherited from proof hypotheses
    semantic: str | None            # "step_size" | "sample_count" | "bound" | ...
    reactivity: Literal["client", "server"]
    affects: list[str]              # beat ids / node ids
```

### SceneSpec — input to both renderers

```python
class Beat(BaseModel):
    id: str
    source_node: str | None         # ProofDAG node this visualizes
    duration: float
    narration: str
    enter: list[ObjectSpec]
    update: list[ActionSpec]
    exit: list[str]
    layout: LayoutConstraints

class SceneSpec(BaseModel):
    title: str
    params: list[ParamSpec]
    beats: list[Beat]
    camera: CameraSpec
    provenance: dict                # ProofDAG hash, verifier tiers used
```

---

## 4. Interactive parameters — the differentiating feature

Parameters are extracted from the question itself, then **bounded by what was
actually proved**.

**Pipeline:** question → Intent Agent emits `ParamSpec[]` → proof kernel attaches
`hypotheses` to each node → `valid_domain` is derived from those hypotheses →
UI renders a control that *knows where the theorem stops holding*.

**Reactivity classification** (decided at compile time by dependency analysis):

- **`client`** — the parameter feeds numeric values into already-computed
  geometry: a dot's position along a precomputed curve, scale, opacity, color,
  camera. Re-evaluated in-browser, zero round-trip, true 60fps.
- **`server`** — the parameter changes *topology*: number of Riemann rectangles,
  objects appearing or disappearing, new LaTeX strings, a different function.
  Round-trips to the geometry serializer.

**Why this matters more than ordinary sliders.** Drag η past `2/L` in the
gradient-descent scene and the iterates diverge — the proved claim "iterates
approach the minimum" becomes *false*. Because the ProofDAG carries the
hypothesis `0 < eta < 2/L`, the UI can shade the invalid region, and the
narration switches from asserting the theorem to explaining why the hypothesis
exists.

Without a verifier, a slider is decoration. With one, **the slider teaches the
theorem's hypotheses.** This is the payoff that connects the AlphaProof half of
the system to the interactive half, and it is not something a Manim wrapper can
do.

---

## 5. Manim: reuse vs. improve

Manim 0.20.1 is vendored at `./manim` (`requires-python = ">=3.11"`, matching
`pyproject.toml`). Install editable so improvements live as tracked patches.

### Reuse as-is

LaTeX→vector-glyph pipeline · Bézier / `VMobject` path algebra ·
`Axes`/`NumberPlane`/`ComplexPlane`/`ThreeDAxes` with `c2p`/`p2c` · `plot`,
`get_area`, `get_riemann_rectangles`, `get_secant_slope_group` · rate functions,
`ValueTracker`, `always_redraw` · `LinearTransformationScene`,
`MovingCameraScene`, 3D camera · ffmpeg muxing and partial-movie caching ·
`TransformMatchingTex` (`transform_matching_parts.py:237`) — the exact primitive
for animating a proof rewrite.

Already better than expected: `tex_file_writing.py:27` `tex_hash()` means LaTeX
output is **already content-addressed**; `hashing.py:333`
`get_hash_from_play_call()` gives **per-animation caching** to build on; and
`typst_mobject.py:153` ships `Typst`/`TypstMath` with a design doc at
`manim/agents/typst_selector.md` for `data-typst-label` sub-expression selection.

### Improve, ranked by impact

**1. SceneSpec IR instead of free-form codegen.** Today the Coding Agent emits
arbitrary Python and `prompts.py` fights it with rules 25–47 — "never index a
Polygon", "keep objects 0.3 units from edges", "never create a new object inside
`FadeOut()`". Every one of those is a bug class that *disappears* when the agent
emits validated JSON and a deterministic compiler emits the Manim code. The
agent chooses what to show; it never remembers API trivia.

**2. Layout solver + frame-bounds/overlap checker.** Manim has `next_to` and
`arrange` and no layout engine. Overlapping text and off-frame objects are the
top visual defect, currently defended only by prompt rules 35–47. A constraint
solver over the SceneSpec plus a mechanical checker turns the Visual Reviewer
from "ask a VLM if it looks OK" into a deterministic pass with a VLM second
opinion.

**3. Scene introspection.** There is no way to ask a Scene "what is on screen at
t=3.2s, with what bounding boxes". Both the Visual Reviewer and the serializer
need it. Add a recording layer snapshotting mobject state per beat.

**4. LaTeX pipeline.** `tools/latex_validator.py:6` "validates" by counting
braces — it passes strings that explode at render time. Replace with real
compilation against Manim's template, run once over the whole ProofDAG *before*
codegen, cached on `tex_hash`. Add a persistent compile daemon, and Typst as the
live-preview fast path (single ~30MB binary, direct SVG, no DVI round-trip).

**5. Beat-level incremental re-render.** Extend `get_hash_from_play_call`
caching to key on SceneSpec beat hashes, so editing beat 7 re-renders beat 7.

---

## 6. Security posture

The sandbox problem largely **dissolves** under this architecture. Once the main
path is `SceneSpec → deterministic compiler → Manim`, no LLM-authored Python is
executed at all — the model emits validated data against a Pydantic schema.

Remaining execution risk is confined to **agent-authored tools** (Phase 7).
Decision: **human-approved registry.** Agents may *propose* a tool with tests;
it lands in `tools/pending/` and enters the registry only after review. This box
carries other people's project directories and four GPUs; the curated-library
outcome is worth the latency.

Note that `tools/code_validator.py:14` only blocks import *names* — it misses
attribute-based escapes such as `().__class__.__bases__[0].__subclasses__()` and
does not block `sys`. It is retained only as a defense-in-depth check on the
legacy path, never as the primary control.

---

## 7. Phases

Each phase has a hard exit criterion. Do not start the next until it passes.

### Phase 0 — Environment (blocking; nothing runs today)

Three confirmed blockers: Manim is not installed (`import manim` only appeared to
work because the vendored `./manim` clone shadows it as a namespace package); no
LaTeX engine is present (`dvisvgm` exists, no `latex`/`pdflatex`); Python is
3.8.8 while the code and Manim both require ≥3.11.

- Create conda env `proofmotion` on Python 3.11
- Move `./manim` → `vendor/manim` to end import shadowing; install editable
  (`pip install -e vendor/manim`) so our patches are tracked
- Install Typst binary (live path) and a minimal TeX Live scheme (export path)
- ffmpeg 7.0.2 already present ✓
- Delete dead code: root `tools.py`, `agent.py`, `generated_scene.py` (duplicates
  of `tools/`, superseded by `agents/`)
- Pin `pydantic>=2.8` in the new env (base conda has 1.10)

**Exit:** `manim -ql vendor/manim/example_scenes/basic.py SquareToCircle` renders,
and a scene containing `MathTex(r"\int_a^b f(x)\,dx")` renders.

### Phase 1 — Core contracts

- Implement `ProofDAG`, `ParamSpec`, `SceneSpec`, `Beat`, `ObjectSpec`,
  `ActionSpec`, `LayoutConstraints`
- Retire hardcoded `schemas/math_plan.py` topic assumptions
- Golden fixtures: three hand-written ProofDAGs (an algebraic identity, a
  calculus derivation, a geometry statement)

**Exit:** schemas round-trip through JSON with validation; fixtures load.

### Phase 2 — Verification tier 0/1 + Formalizer

- SymPy verifier with numerical spot-check (equality under random sampling
  before symbolic `simplify`, which catches most false claims fast)
- Z3 tier for inequalities and linear/nonlinear arithmetic
- Compile-based LaTeX validator replacing the brace counter
- Formalizer Agent: NL → formal statement, over OpenRouter
- Provider layer: expand `llm/base_client.py` into a real abstraction with
  retries, structured output, and token accounting

**Exit:** the system verifies a correct multi-step identity chain end-to-end and
**rejects a deliberately wrong one**, with a certificate for each node.

### Phase 3 — Proof search kernel (the AlphaProof-shaped part)

- `ProofState` + best-first frontier + backtracking
- LLM-as-policy: propose next step or auxiliary construction
- Verifier-as-oracle: accept / reject / new state
- Subgoal decomposition (Draft → Sketch → Prove); recurse on failed holes
- Shared fact store across parallel expansions
- `Checkpointer` protocol (SQLite) for resumable searches

**Exit:** decompose and prove a theorem requiring ≥4 dependent steps, emitting a
ProofDAG with hypotheses attached to every node.

### Phase 4 — SceneSpec compiler + Manim improvements

- ProofDAG → SceneSpec (beats from topological order; pacing from node depth)
- Constraint-based layout solver
- Frame-bounds + overlap checker
- **Deterministic** SceneSpec → Manim compiler (no LLM in this path)
- Scene introspection / recording layer

**Exit:** an MP4 renders from a ProofDAG with **zero LLM-written Python**, and the
overlap checker reports clean.

### Phase 5 — Geometry serializer + WebGL runtime (Option C)

- Serializer: Manim-computed geometry → flat scene graph (paths, transforms,
  colors, keyframes) as JSON
- JS/WebGL renderer with local interpolation
- KaTeX for in-browser math (same LaTeX source as the export path)
- Timeline: play/pause/scrub

**Exit:** a scene plays in the browser at 60fps and is visually equivalent to its
MP4 export.

### Phase 6 — Interactive parameters

- ParamSpec extraction in the Intent Agent
- Client/server reactivity classification via dependency analysis
- `valid_domain` derived from ProofDAG hypotheses
- Controls bound to Manim `ValueTracker`s on the export path, to local
  re-evaluation on the client path
- Invalid-region shading + narration switching

**Exit:** drag η in the gradient-descent scene past `2/L`, watch the iterates
diverge, and see the violated hypothesis surfaced in the UI.

### Phase 7 — Review loop, geometry tier, tool registry

- Visual Reviewer: mechanical checks first, VLM second opinion
- Math Reviewer over the ProofDAG certificates
- Debug Agent — now a *small* job, since it repairs a spec, not free-form Python
- DDAR / Euclidean geometry tier (AlphaGeometry-style; produces the most
  animatable proofs of any tier)
- Tool registry with the human-approval gate

**Exit:** the full loop from the original diagram runs unattended on a fresh
question.

### Deferred

- **Lean 4 + mathlib tier.** Weeks of work, multi-GB toolchain. Its proofs also
  animate *worst* of any tier — `simp`, `linarith`, and `omega` each compress
  hundreds of inferences into one opaque call. Resolution when we get there: the
  informal DSP draft is the animation spine, Lean is the certificate. Open-weight
  provers (DeepSeek-Prover-V2-7B, Goedel-Prover, Kimina-Prover) fit on a single
  A6000 — **verify current model sizes and availability before committing.**
- **Physics.** Does not fit the proof frame at all; there is no proof engine for
  mechanics or E&M. Verification there means dimensional analysis, conservation
  checks, and numerical integration against known solutions — a separate verifier
  tier, not a proof tier. Decide scope after Phase 6.

---

## 8. Target repo layout

```
proofmotion/
  contracts/        ProofDAG, SceneSpec, ParamSpec        (Phase 1)
  runtime/          orchestrator, checkpointer, state bus (Phase 1)
  llm/              provider abstraction, OpenRouter      (Phase 2)
  verify/           sympy_, numeric_, z3_, ddar_, lean_   (Phase 2, 7)
  search/           proof kernel, frontier, fact store    (Phase 3)
  agents/           intent, planner, formalizer, pedagogy,
                    visual_director, reviewers, debug
  compile/          layout solver, scenespec→manim,
                    geometry serializer                    (Phase 4, 5)
  web/              WebGL runtime, controls, timeline      (Phase 5, 6)
  tools/            curated registry + pending/            (Phase 7)
vendor/manim/       patched Manim 0.20.1, editable install
```

---

## 9. Risks

| Risk | Mitigation |
|---|---|
| Serialization surface too wide for Option C | Fall back to Option B (headless Manim OpenGL, stream frames over WebRTC). The GL renderer and shaders already exist; 4× A6000 with EGL makes it fast. Decide at the Phase 5 gate. |
| Proof search latency (minutes to hours) | Checkpointing + aggressive tier routing — never invoke a heavy tier when SymPy suffices. Most animatable math is Tier 0. |
| LaTeX/Typst divergence between live and export paths | LaTeX stays canonical in the ProofDAG. Typst and KaTeX are consumers. Add a visual-diff test at the Phase 5 gate. |
| Scope ("basic to advanced" + physics) | Tiers 0 and 2 first — they cover most of what people want animated *and* produce the most animatable proofs. Lean and physics explicitly deferred. |
| Vendored Manim drifting from upstream | Patches tracked in-repo; pin the upstream commit; re-base deliberately, never automatically. |

---

## 10. Open items

1. **Physics scope** — in or out of v1? (Recommendation: out; revisit after Phase 6.)
2. **Prover model choice** for the deferred Lean tier — verify current
   open-weight options against live sources before committing.
3. **Sandbox decision** was folded into §6 rather than answered directly; confirm
   the human-approved registry is acceptable.
