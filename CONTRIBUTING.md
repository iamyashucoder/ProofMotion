# Contributing

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[render,dev]"
pytest
```

## Contribution rules

- Add or update tests for deterministic planning, mathematics, and tool behavior.
- Keep generated Manim programs inside the restricted validator policy.
- Do not treat LLM output as verified mathematics; validate it through tools.
- Add a tested Manim example before introducing an API pattern to generated code.
- Keep draft preview/editing available before high-quality final rendering.
