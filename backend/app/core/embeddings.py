from __future__ import annotations

from abc import ABC, abstractmethod
from functools import lru_cache

from loguru import logger

from app.config import get_settings

settings = get_settings()


class BaseEmbedder(ABC):
    dim: int

    @abstractmethod
    def embed(self, texts: list[str]) -> list[list[float]]:
        """Embed a batch of texts, returning one vector per text."""
        raise NotImplementedError

    def embed_one(self, text: str) -> list[float]:
        return self.embed([text])[0]


class SentenceTransformersEmbedder(BaseEmbedder):
    """Local, free, no API key required. Good default for a personal project."""

    def __init__(self, model_name: str, dim: int) -> None:
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading local embedding model: {model_name}")
        self._model = SentenceTransformer(model_name)
        self.dim = dim

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return vectors.tolist()


@lru_cache
def get_embedder() -> BaseEmbedder:
    return SentenceTransformersEmbedder(settings.embedding_model, settings.embedding_dim)
