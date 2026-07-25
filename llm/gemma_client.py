import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class GemmaClient:
    """Small OpenRouter client; all agents share this one implementation."""

    def __init__(self) -> None:
        self.model = os.getenv("OPENROUTER_MODEL", "google/gemma-3-27b-it")
        self.api_key = os.getenv("OPENROUTER_API_KEY")

    @property
    def available(self) -> bool:
        return bool(self.api_key)

    def complete(self, system_prompt: str, user_prompt: str, *, max_tokens: int = 4000) -> str | None:
        if not self.api_key:
            return None
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=self.api_key)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception:
            return None
