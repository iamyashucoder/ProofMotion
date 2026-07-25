from llm.base_client import LLMClient
from agents.manim_coder import clean_code


def classify_error(error: str) -> str:
    lowered = error.lower()
    if "syntaxerror" in lowered: return "python_syntax"
    if "latex" in lowered or "tex" in lowered: return "latex"
    if "attributeerror" in lowered or "typeerror" in lowered: return "manim_api"
    if "timed out" in lowered: return "performance"
    return "general_render"


def repair_code(client: LLMClient | None, original_prompt: str, code: str, error: str) -> str | None:
    if not client:
        return None
    prompt = f"Repair this Manim 0.20.1 program. Error category: {classify_error(error)}. Return code only.\nRequest: {original_prompt}\nCode:\n{code}\nError:\n{error}"
    fixed = client.complete("You are a careful Manim repair agent. Preserve verified mathematics and the GeneratedScene class.", prompt)
    return clean_code(fixed) if fixed else None
