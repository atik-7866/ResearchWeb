from __future__ import annotations

import json
from abc import ABC, abstractmethod
from functools import lru_cache

from loguru import logger

from app.config import get_settings

settings = get_settings()


class BaseLLM(ABC):
    provider_name: str
    model_name: str

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        """Return the raw text completion for a system+user prompt pair."""
        raise NotImplementedError

    def complete_json(self, system: str, user: str, max_tokens: int = 1500) -> dict | None:
        """
        Ask for a JSON response and parse it. Returns None (not an
        exception) on parse failure so callers can fall back gracefully -
        an LLM formatting slip shouldn't 500 the whole request.
        """
        raw = self.complete(system, user, max_tokens=max_tokens)
        cleaned = raw.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:]
        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError:
            logger.warning(f"LLM did not return valid JSON, falling back to raw text. First 200 chars: {raw[:200]}")
            return None


class GroqLLM(BaseLLM):
    def __init__(self, model: str, api_key: str) -> None:
        from groq import Groq

        if not api_key:
            raise ValueError("GROQ_API_KEY is not set")
        self._client = Groq(api_key=api_key)
        self.provider_name = "groq"
        self.model_name = model

    def complete(self, system: str, user: str, max_tokens: int = 1500) -> str:
        response = self._client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content or ""


@lru_cache
def get_llm() -> BaseLLM:
    return GroqLLM(settings.llm_model, settings.groq_api_key)
