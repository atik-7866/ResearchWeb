from __future__ import annotations

from functools import lru_cache

from langchain_core.language_models.chat_models import BaseChatModel

from app.config import get_settings

settings = get_settings()


@lru_cache
def get_chat_model() -> BaseChatModel:
    from langchain_groq import ChatGroq

    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not set")
    return ChatGroq(model=settings.llm_model, api_key=settings.groq_api_key, max_tokens=2000)
