"""
Service layer over Neo4jClient's Phase 2 traversal methods. Formats raw
Cypher results into the typed response shapes in schemas/graph.py, and
raises clear errors when the requested paper/topic/author doesn't exist
rather than silently returning empty results (empty vs. not-found is
an important distinction for the frontend).
"""
from __future__ import annotations

from app.db.neo4j_client import get_neo4j_client
from app.schemas.graph import (
    AuthorProfileResponse,
    CitationChainResponse,
    CitationChainSegment,
    CitationPathResponse,
    PapersBetweenTopicsResponse,
    RelatedPapersResponse,
    TopicOverviewResponse,
    TopicPapersResponse,
    TopicsListResponse,
)


def related_papers(paper_id: str, limit: int = 10) -> RelatedPapersResponse:
    neo4j = get_neo4j_client()
    results = neo4j.find_related_papers(paper_id, limit=limit)
    return RelatedPapersResponse(paper_id=paper_id, count=len(results), results=results)


def citation_chain(paper_id: str, depth: int = 2, direction: str = "outgoing") -> CitationChainResponse:
    neo4j = get_neo4j_client()
    raw = neo4j.find_citation_chain(paper_id, depth=depth, direction=direction)
    segments = [CitationChainSegment(hops=r["hops"], chain=r["chain"]) for r in raw]
    return CitationChainResponse(paper_id=paper_id, direction=direction, depth=depth, paths=segments)


def citation_path(from_id: str, to_id: str, max_hops: int = 6) -> CitationPathResponse:
    neo4j = get_neo4j_client()
    result = neo4j.find_citation_path(from_id, to_id, max_hops=max_hops)
    if not result:
        return CitationPathResponse(from_id=from_id, to_id=to_id, found=False)
    return CitationPathResponse(
        from_id=from_id, to_id=to_id, found=True, hops=result["hops"], chain=result["chain"]
    )


def foundational_papers(topic: str, limit: int = 10) -> TopicPapersResponse:
    neo4j = get_neo4j_client()
    results = neo4j.find_foundational_papers(topic, limit=limit)
    return TopicPapersResponse(
        topic=topic,
        label="foundational",
        count=len(results),
        results=results,
        caveat=(
            "Heuristic ranking by citation count and publication year within this "
            "topic's indexed papers - not a verified claim of historical priority."
        ),
    )


def recent_papers(topic: str, limit: int = 10) -> TopicPapersResponse:
    neo4j = get_neo4j_client()
    results = neo4j.find_recent_papers(topic, limit=limit)
    return TopicPapersResponse(topic=topic, label="recent", count=len(results), results=results)


def topic_papers(topic: str, limit: int = 20, sort: str = "citations") -> TopicPapersResponse:
    neo4j = get_neo4j_client()
    results = neo4j.get_topic_papers(topic, limit=limit, sort=sort)
    return TopicPapersResponse(topic=topic, label="all", count=len(results), results=results)


def papers_between_topics(topic_a: str, topic_b: str, limit: int = 10) -> PapersBetweenTopicsResponse:
    neo4j = get_neo4j_client()
    result = neo4j.find_papers_between_topics(topic_a, topic_b, limit=limit)
    return PapersBetweenTopicsResponse(
        topic_a=topic_a,
        topic_b=topic_b,
        direct_overlap=result["direct_overlap"],
        citation_bridges=result["citation_bridges"],
    )


def author_profile(author_name: str) -> AuthorProfileResponse | None:
    neo4j = get_neo4j_client()
    result = neo4j.get_author_profile(author_name)
    if not result:
        return None
    return AuthorProfileResponse(
        name=result["name"],
        paper_count=len(result["papers"]),
        papers=result["papers"],
        topics=result["topics"],
        coauthors=result["coauthors"],
    )


def list_topics(limit: int = 30) -> TopicsListResponse:
    neo4j = get_neo4j_client()
    results = neo4j.list_topics(limit=limit)
    return TopicsListResponse(count=len(results), topics=results)


def topic_overview(topic: str) -> TopicOverviewResponse:
    neo4j = get_neo4j_client()
    result = neo4j.get_topic_overview(topic)
    return TopicOverviewResponse(**result)
