"""
Qdrant wrapper for storing/searching paper embeddings.

Each point stored:
    id       -> stable integer hash of paper_id (Qdrant point IDs must be
                int or UUID; we derive a deterministic UUID from paper_id)
    vector   -> embedding of "title + abstract"
    payload  -> paper_id, title, authors, year, topics, doi, venue
                (kept in sync with Neo4j so search results are self-contained)
"""
from __future__ import annotations

import uuid
from functools import lru_cache

from loguru import logger
from qdrant_client import QdrantClient as _QdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings
from app.schemas.paper import NormalizedPaper

settings = get_settings()

# Deterministic namespace so the same paper_id always maps to the same point ID,
# making upserts idempotent across ingestion re-runs.
_NAMESPACE = uuid.UUID("6f1c1f2e-6f2e-4e2a-9c0a-2a7c6f1c1f2e")


def _point_id(paper_id: str) -> str:
    return str(uuid.uuid5(_NAMESPACE, paper_id))


class QdrantWrapper:
    def __init__(self, host: str, port: int, collection: str, dim: int, api_key: str = "", https: bool = False) -> None:
        self._client = _QdrantClient(host=host, port=port, api_key=api_key or None, https=https)
        self.collection = collection
        self.dim = dim

    def ensure_collection(self) -> None:
        existing = [c.name for c in self._client.get_collections().collections]
        if self.collection in existing:
            return
        self._client.create_collection(
            collection_name=self.collection,
            vectors_config=qmodels.VectorParams(size=self.dim, distance=qmodels.Distance.COSINE),
        )
        logger.info(f"Created Qdrant collection '{self.collection}' (dim={self.dim})")

    def upsert_paper(self, paper: NormalizedPaper, vector: list[float]) -> None:
        point = qmodels.PointStruct(
            id=_point_id(paper.paper_id),
            vector=vector,
            payload={
                "paper_id": paper.paper_id,
                "title": paper.title,
                "authors": [a.name for a in paper.authors],
                "year": paper.year,
                "topics": paper.topics,
                "doi": paper.doi,
                "arxiv_id": paper.arxiv_id,
                "venue": paper.venue,
                "cited_by_count": paper.cited_by_count,
            },
        )
        self._client.upsert(collection_name=self.collection, points=[point])

    def search(self, vector: list[float], top_k: int = 10) -> list[dict]:
        """
        Uses query_points (the current, non-deprecated Qdrant API) rather
        than the older search() method, which some client versions have
        already removed.
        """
        response = self._client.query_points(
            collection_name=self.collection, query=vector, limit=top_k, with_payload=True
        )
        results = []
        for hit in response.points:
            payload = hit.payload or {}
            payload["relevance_score"] = round(hit.score, 4)
            results.append(payload)
        return results

    def count(self) -> int:
        return self._client.count(collection_name=self.collection).count


@lru_cache
def get_qdrant_client() -> QdrantWrapper:
    return QdrantWrapper(
        host=settings.qdrant_host,
        port=settings.qdrant_port,
        collection=settings.qdrant_collection,
        dim=settings.embedding_dim,
        api_key=settings.qdrant_api_key,
        https=settings.qdrant_https,
    )
