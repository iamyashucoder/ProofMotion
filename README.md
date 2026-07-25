# Math Manim Agents

`math-manim-agents` is a preview-first, mathematically grounded agent system
for educational Manim animations. It turns a request into a structured intent,
verified mathematical plan, pedagogy plan, storyboard, safe Manim code, and a
project-scoped preview that can be edited before final rendering.

## Install

```bash
git clone https://github.com/your-org/math-manim-agents.git
cd math-manim-agents
python -m pip install -e ".[render,dev]"
```

## Run a draft

```bash
math-manim "Explain gradient descent visually for a beginner"
```

The command saves a unique folder in `generated_projects/` and renders a
low-quality draft preview. It does not create a final video by default.

## Edit while working

Start the local editor using the project id printed by `main.py`:

```bash
math-manim-preview generated_projects/<project-id>
```

Open `http://127.0.0.1:8765`. The editor lets you review and save the
storyboard, edit the generated Manim source, and render a new draft preview in
place. This happens before the final video stage.

## Final render

After approving the draft:

```bash
math-manim "Explain gradient descent visually for a beginner" --final
```

## Current supported first-release topics

- Functions and graphs
- Introductory calculus
- Basic geometry
- Arrays and algorithms
- Basic linear algebra
- Probability demonstrations

The deterministic planning and verification paths work without an API key.
When `OPENROUTER_API_KEY` is configured, Gemma can generate and repair Manim
code while symbolic and validation tools remain the source of truth for
mathematics and execution safety. See [CONTRIBUTING.md](CONTRIBUTING.md) for
development rules.

# ProofMotion
