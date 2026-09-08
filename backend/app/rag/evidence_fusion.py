"""
Evidence Fusion: the second step of Hybrid RAG.

Takes the outputs of vector search + graph traversal and combines them
into one structured bundle with three clearly separated evidence types:

    1. vector_evidence   - "these papers are semantically similar to the query"
    2. graph_evidence     - "these papers are structurally connected"
       (citation links, shared topics, foundational/recent framing)
    3. (LLM interpretation is added later, in hybrid_service.py - fusion
        itself does not interpret anything, it only assembles facts)

Keeping fusion free of any LLM call means the evidence bundle itself is a
useful, inspectable artifact - exactly what Phase 11's evaluation compares
across vector-only / graph-only / hybrid retrieval.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.db.neo4j_client import get_neo4j_client
from app.rag.query_analyzer import TopicMatch, detect_topics
from app.schemas.paper import PaperOut
from app.services import paper_service


@dataclass
class GraphEvidence:
    citation_links_among_results: list[dict] = field(default_factory=list)
    related_via_graph: dict[str, list[dict]] = field(default_factory=dict)  # paper_id -> related papers
    topic_matches: list[dict] = field(default_factory=list)  # detected topics + foundational/recent papers


@dataclass
class EvidenceBundle:
    query: str
    vector_evidence: list[PaperOut]
    graph_evidence: GraphEvidence
    topics_detected: list[str]


def fuse_evidence(query: str, vector_top_k: int = 8, related_per_paper: int = 3) -> EvidenceBundle:
    neo4j = get_neo4j_client()

    # 1. Vector retrieval (Phase 1)
    vector_hits = paper_service.semantic_search(query, top_k=vector_top_k)
    vector_paper_ids = [p.paper_id for p in vector_hits]

    # 2. Graph retrieval, anchored on the vector hits + detected topics (Phase 2 queries)
    citation_links = neo4j.get_citation_edges_among(vector_paper_ids)

    related_via_graph: dict[str, list[dict]] = {}
    for paper_id in vector_paper_ids[:5]:  # cap to keep this fast
        related = neo4j.find_related_papers(paper_id, limit=related_per_paper)
        if related:
            related_via_graph[paper_id] = related

    topic_matches: list[TopicMatch] = detect_topics(query)
    topic_evidence = []
    for match in topic_matches:
        topic_evidence.append(
            {
                "topic": match.topic,
                "paper_count": match.paper_count,
                "overlap_score": match.overlap_score,
                "foundational_papers": neo4j.find_foundational_papers(match.topic, limit=3),
                "recent_papers": neo4j.find_recent_papers(match.topic, limit=3),
            }
        )

    graph_evidence = GraphEvidence(
        citation_links_among_results=citation_links,
        related_via_graph=related_via_graph,
        topic_matches=topic_evidence,
    )

    return EvidenceBundle(
        query=query,
        vector_evidence=vector_hits,
        graph_evidence=graph_evidence,
        topics_detected=[m.topic for m in topic_matches],
    )
