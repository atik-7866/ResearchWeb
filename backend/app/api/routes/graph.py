"""
Phase 2 graph endpoints. These sit alongside /papers/* (vector search,
Phase 1) rather than replacing it - Phase 4 (Hybrid RAG) will combine
both under /research/query. Until then, the frontend/agent can call
each independently, which is also how the Phase 11 evaluation compares
"graph-only" vs "vector-only" vs "hybrid" retrieval quality.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.graph import (
    AuthorProfileResponse,
    CitationChainResponse,
    CitationPathResponse,
    PapersBetweenTopicsResponse,
    RelatedPapersResponse,
    TopicOverviewResponse,
    TopicPapersResponse,
    TopicsListResponse,
)
from app.services import graph_service, paper_service

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/papers/{paper_id}/related", response_model=RelatedPapersResponse)
def get_related_papers(paper_id: str, limit: int = Query(default=10, ge=1, le=50)):
    if not paper_service.get_paper_detail(paper_id):
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    return graph_service.related_papers(paper_id, limit=limit)


@router.get("/papers/{paper_id}/citation-chain", response_model=CitationChainResponse)
def get_citation_chain(
    paper_id: str,
    depth: int = Query(default=2, ge=1, le=5),
    direction: str = Query(default="outgoing", pattern="^(outgoing|incoming)$"),
):
    """
    direction='outgoing': what this paper cites, going back toward
    foundational work. direction='incoming': what cites this paper,
    going forward toward newer influenced work.
    """
    if not paper_service.get_paper_detail(paper_id):
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    return graph_service.citation_chain(paper_id, depth=depth, direction=direction)


@router.get("/citation-path", response_model=CitationPathResponse)
def get_citation_path(
    from_id: str = Query(..., description="Source paper_id"),
    to_id: str = Query(..., description="Target paper_id"),
    max_hops: int = Query(default=6, ge=1, le=8),
):
    return graph_service.citation_path(from_id, to_id, max_hops=max_hops)


@router.get("/topics", response_model=TopicsListResponse)
def get_topics(limit: int = Query(default=30, ge=1, le=200)):
    """Browse indexed topics by paper count - useful for a 'popular topics' UI widget."""
    return graph_service.list_topics(limit=limit)


@router.get("/topics/{topic}/papers", response_model=TopicPapersResponse)
def get_topic_papers(
    topic: str,
    limit: int = Query(default=20, ge=1, le=100),
    sort: str = Query(default="citations", pattern="^(citations|year|oldest)$"),
):
    result = graph_service.topic_papers(topic, limit=limit, sort=sort)
    if result.count == 0:
        raise HTTPException(status_code=404, detail=f"No papers found for topic '{topic}'")
    return result


@router.get("/topics/{topic}/foundational", response_model=TopicPapersResponse)
def get_foundational_papers(topic: str, limit: int = Query(default=10, ge=1, le=50)):
    result = graph_service.foundational_papers(topic, limit=limit)
    if result.count == 0:
        raise HTTPException(status_code=404, detail=f"No papers found for topic '{topic}'")
    return result


@router.get("/topics/{topic}/recent", response_model=TopicPapersResponse)
def get_recent_papers(topic: str, limit: int = Query(default=10, ge=1, le=50)):
    result = graph_service.recent_papers(topic, limit=limit)
    if result.count == 0:
        raise HTTPException(status_code=404, detail=f"No papers found for topic '{topic}'")
    return result


@router.get("/topics/{topic}/overview", response_model=TopicOverviewResponse)
def get_topic_overview(topic: str):
    return graph_service.topic_overview(topic)


@router.get("/topics-between", response_model=PapersBetweenTopicsResponse)
def get_papers_between_topics(
    topic_a: str = Query(...),
    topic_b: str = Query(...),
    limit: int = Query(default=10, ge=1, le=50),
):
    return graph_service.papers_between_topics(topic_a, topic_b, limit=limit)


@router.get("/authors/{author_name}", response_model=AuthorProfileResponse)
def get_author(author_name: str):
    result = graph_service.author_profile(author_name)
    if not result:
        raise HTTPException(status_code=404, detail=f"Author '{author_name}' not found")
    return result
