"""
Query Analyzer: the first step of Hybrid RAG.

Its only job is deciding *which indexed topics* a free-text query is
actually about, so the graph-retrieval step knows what to look up.
Without this, every query would either need to run every possible graph
query (wasteful) or none (defeats the point of Hybrid RAG).

This is deliberately simple (token overlap, no embeddings, no LLM call)
because it only needs to work against a controlled vocabulary - the
topic names already sitting in Neo4j from ingestion. A cheap, explainable
heuristic beats a black-box classifier here. The Phase 4 agent can later
replace this with a tool-calling LLM step; the interface stays the same.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from app.db.neo4j_client import get_neo4j_client

_STOPWORDS = {
    "the", "a", "an", "of", "in", "on", "for", "with", "and", "or", "to",
    "is", "are", "how", "what", "why", "does", "do", "between", "using",
    "based", "via", "vs", "versus", "compare", "comparison", "show", "me",
    "explain", "research", "paper", "papers", "about",
}


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {w for w in words if w not in _STOPWORDS and len(w) > 2}


@dataclass
class TopicMatch:
    topic: str
    paper_count: int
    overlap_score: float


def detect_topics(query: str, max_topics: int = 3, candidate_pool: int = 150) -> list[TopicMatch]:
    """
    Score every indexed topic by token (Jaccard-style) overlap with the
    query, and return the top matches above a minimum threshold.

    `candidate_pool` caps how many of the most-populous indexed topics we
    even consider, since scanning every topic in a large graph on every
    query would be wasteful; the most-cited topics are also the most
    likely to matter to a research question anyway.
    """
    neo4j = get_neo4j_client()
    all_topics = neo4j.list_topics(limit=candidate_pool)

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    scored: list[TopicMatch] = []
    for entry in all_topics:
        topic_name = entry["topic"]
        topic_tokens = _tokenize(topic_name)
        if not topic_tokens:
            continue
        overlap = query_tokens & topic_tokens
        if not overlap:
            continue
        # Weighted toward how much of the *topic's* meaning is covered,
        # since topic names are short and specific (e.g. "Retrieval-Augmented
        # Generation") - covering most of a short topic name is a strong signal.
        score = len(overlap) / len(topic_tokens)
        if score >= 0.5:
            scored.append(TopicMatch(topic=topic_name, paper_count=entry["paper_count"], overlap_score=round(score, 2)))

    scored.sort(key=lambda t: (t.overlap_score, t.paper_count), reverse=True)
    return scored[:max_topics]
