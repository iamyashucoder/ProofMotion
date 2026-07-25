# ProofMotion

**Verified mathematics, animated.**

ProofMotion turns a mathematical question into an animation whose every frame is
backed by a machine-checkable certificate. An AlphaProof-style neuro-symbolic
kernel searches for a proof — an LLM proposes steps, a formal engine accepts or
rejects them — and the resulting proof DAG is compiled into an interactive scene
rendered live in the browser and exported through Manim.

Because the proof carries its hypotheses, the interactive controls know where the
theorem stops holding. Drag a learning rate past its convergence bound and you
watch the iterates diverge, with the violated hypothesis surfaced in the UI.
Without a verifier a slider is decoration; with one, **the slider teaches the
theorem's hypotheses.**

See [PLAN.md](PLAN.md) for the full architecture and phased build plan.

---

## Status: Phase 0 complete

The environment is built and both math typesetting paths render. **The pipeline
itself is still the pre-existing scaffold** — a linear function with hardcoded
topic branches, not yet the architecture described in `PLAN.md`. Phase 1 (core
contracts: `ProofDAG`, `SceneSpec`, `ParamSpec`) is next.

| Component | State |
|---|---|
| Python 3.11 + uv project | ✅ working |
| Manim 0.20.1 (vendored, editable) | ✅ renders |
| Typst math (`TypstMath`) | ✅ renders |
| LaTeX math (`MathTex`, via TinyTeX) | ✅ renders |
| SymPy / Z3 verification tiers | ⏳ Phase 2 |
| Proof search kernel | ⏳ Phase 3 |
| SceneSpec compiler | ⏳ Phase 4 |
| WebGL runtime | ⏳ Phase 5 |
| Interactive parameters | ⏳ Phase 6 |

## Setup

Requires [uv](https://docs.astral.sh/uv/). No root access needed.

```bash
git clone https://github.com/MAXNORM8650/ProofMotion.git
cd ProofMotion

# Vendored Manim — patched in later phases, so it is a clone, not a pin.
git clone https://github.com/ManimCommunity/manim.git vendor/manim
git -C vendor/manim checkout "$(cat vendor/MANIM_PINNED_COMMIT.txt)"

source scripts/env.sh     # uv cache, managed Python, and TinyTeX locations
uv sync --extra verify
```

`scripts/env.sh` exists because this machine's root partition is full and has no
sudo: uv's cache, uv's managed interpreters, and TinyTeX all live on a data
volume. Edit `PROOFMOTION_TOOLS` in that file for a different host.

### TeX

`TypstMath` needs no external binary — manim 0.20.1 drives Typst through a Python
package. `MathTex`/`Tex` need a TeX engine, installed here as userspace TinyTeX:

```bash
tlmgr install standalone preview doublestroke ragged2e physics babel-english amsmath amsfonts
```

## Verify the install

```bash
uv run manim -ql vendor/manim/example_scenes/basic.py SquareToCircle
uv run pytest
```

## Run the current scaffold

```bash
uv run proofmotion "Explain gradient descent visually for a beginner"
uv run proofmotion-preview generated_projects/<project-id>
```

Deterministic planning and verification run without an API key. With a provider
configured, an LLM generates and repairs Manim code, while symbolic and
validation tools remain the source of truth for mathematics and safety.

## Model providers

ProofMotion is provider-agnostic. Every backend speaks the OpenAI
chat-completions wire format, so one implementation (`llm/providers.py`) covers
all of them. Select with `PROOFMOTION_LLM_PROVIDER`:

```bash
uv run proofmotion --provider openai   "..."
uv run proofmotion --provider deepseek "..."
uv run proofmotion --provider vllm     "..."   # local, on the A6000s
PROOFMOTION_LLM_PROVIDER=openai uv run proofmotion "..."   # or set it once
```

| Provider | Key | Model env var | Default |
|---|---|---|---|
| `openai` | `OPENAI_API_KEY` | `OPENAI_MODEL` | `gpt-5.2` |
| `deepseek` | `DEEPSEEK_API_KEY` | `DEEPSEEK_MODEL` | `deepseek-v4-pro` |
| `openrouter` | `OPENROUTER_API_KEY` | `OPENROUTER_MODEL` | `google/gemma-4-26b-a4b-it:free` |
| `vllm` | not required | `VLLM_MODEL` | — (set `VLLM_BASE_URL`) |

The agent loop needs tool calling, so the provider must support it. OpenAI and
DeepSeek both do. **OpenRouter `:free` endpoints generally do not** — they route
to upstreams that accept the `tools` parameter and silently ignore it, returning
prose instead, and `provider.require_parameters` will not force a tool-capable
route. Use free models for smoke tests only; the paid variants work.

OpenAI's gpt-5 family rejects `max_tokens` and requires `max_completion_tokens`,
while DeepSeek and OpenRouter expect `max_tokens`, so the parameter name is set
per provider rather than hardcoded.

DeepSeek serves exactly two model ids, `deepseek-v4-pro` and `deepseek-v4-flash`,
and supports extended thinking:

```bash
DEEPSEEK_MODEL=deepseek-v4-flash
DEEPSEEK_THINKING=1              # sends {"thinking": {"type": "enabled"}}
DEEPSEEK_REASONING_EFFORT=high   # only sent when thinking is enabled
```

Reasoning traces come back on `Completion.reasoning` when the model exposes
them. Phase 3's proof kernel uses those traces as evidence when scoring which
candidate proof steps are worth expanding.

A provider failure raises `LLMError` rather than returning `None`. Silently
degrading to template output would hide the cause; `None` means only "this
provider has no key configured", which selects the deterministic path.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development rules.
