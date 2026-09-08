"""
Service layer: keeps API route handlers thin and keeps DB-specific
logic out of the HTTP layer. Phase 1 covers semantic search + basic
paper lookups; Phase 4 (Hybrid RAG) will add a HybridRetrievalService
here that combines this with graph_service queries.
"""
from __future__ import annotations

from app.core.embeddings import get_embedder
from app.db.neo4j_client import get_neo4j_client
from app.db.qdrant_client import get_qdrant_client
from app.schemas.paper import PaperOut


def semantic_search(query: str, top_k: int = 10) -> list[PaperOut]:
    embedder = get_embedder()
    qdrant = get_qdrant_client()

    vector = embedder.embed_one(query)
    hits = qdrant.search(vector, top_k=top_k)

    return [
        PaperOut(
            paper_id=hit["paper_id"],
            title=hit["title"],
            authors=hit.get("authors", []),
            year=hit.get("year"),
            venue=hit.get("venue"),
            doi=hit.get("doi"),
            arxiv_id=hit.get("arxiv_id"),
            topics=hit.get("topics", []),
            cited_by_count=hit.get("cited_by_count", 0),
            relevance_score=hit.get("relevance_score"),
        )
        for hit in hits
    ]


def get_paper_detail(paper_id: str) -> dict | None:
    neo4j = get_neo4j_client()
    node = neo4j.get_paper(paper_id)
    if not node:
        return None
    citations = neo4j.get_citations(paper_id)
    return {**node, **citations}


def get_paper_citations(paper_id: str) -> dict:
    neo4j = get_neo4j_client()
    return neo4j.get_citations(paper_id)
