"""
Tools the Phase 4 agent can choose to call.

Every tool here is a thin wrapper around services already built and
tested in Phases 1-3 (paper_service, graph_service) - the agent doesn't
get new retrieval capabilities, it gets to *decide* which existing
capabilities are relevant to a given question instead of always running
Phase 3's fixed vector-then-graph pipeline.

Tool names intentionally match a subset of the original spec
(search_papers, find_citations, find_related_papers, find_author,
find_topic_papers, find_citation_path, compare_papers as of Phase 5,
build_reading_path as of Phase 6). analyze_research_trend and
find_candidate_research_gaps are NOT included yet - they don't exist
until Phases 7-8. Giving the agent a tool name for a capability that
isn't implemented would let it "successfully" call a stub and
hallucinate a confident-sounding result; better to have a smaller,
honest tool list that grows with each phase.

Every tool returns a compact JSON string (not a Python object) - that's
the wire format LangChain sends back to the LLM as a ToolMessage, and
compact JSON keeps token usage down across a multi-tool-call reasoning
loop.
"""
from __future__ import annotations

import json

from langchain_core.tools import tool

from app.services import comparison_service, graph_service, paper_service, reading_path_service


def _compact(obj) -> str:
    """Serialize tool output compactly, dropping None fields to save tokens."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump(exclude_none=True)
    return json.dumps(obj, default=str, separators=(",", ":"))


@tool
def search_papers(query: str, top_k: int = 8) -> str:
    """
    Semantic search over indexed papers by meaning, not keyword matching.
    Use this first for almost any research question to find a starting
    set of relevant papers. Returns paper_id, title, year, authors,
    topics, citation count, and a relevance score for each result.
    """
    results = paper_service.semantic_search(query, top_k=top_k)
    return _compact([r.model_dump(exclude_none=True) for r in results])


@tool
def find_citations(paper_id: str) -> str:
    """
    Get the papers a given paper cites (references) and the papers that
    cite it (cited_by), from the citation graph. Use this to understand
    what a paper builds on or how it has been used by later work.
    """
    result = paper_service.get_paper_citations(paper_id)
    return _compact(result)


@tool
def find_related_papers(paper_id: str, limit: int = 8) -> str:
    """
    Find papers related to a given paper through shared topics and/or
    shared authors in the graph (not semantic similarity - use
    search_papers for that). Good for "what else is like this paper"
    questions once you already have a paper_id.
    """
    result = graph_service.related_papers(paper_id, limit=limit)
    return _compact(result)


@tool
def find_citation_path(from_id: str, to_id: str) -> str:
    """
    Find the shortest citation path between two specific papers (by
    paper_id) in either citation direction. Use this to answer "how are
    these two specific papers connected" questions.
    """
    result = graph_service.citation_path(from_id, to_id)
    return _compact(result)


@tool
def find_author(author_name: str) -> str:
    """
    Look up an author's profile: their papers, the topics they work on,
    and their co-authors, from the graph. Use this for questions about a
    specific researcher.
    """
    result = graph_service.author_profile(author_name)
    if result is None:
        return json.dumps({"error": f"No author found matching '{author_name}'"})
    return _compact(result)


@tool
def list_topics(limit: int = 25) -> str:
    """
    List the topics actually indexed in the graph, ranked by paper count.
    Call this BEFORE find_topic_papers / find_foundational_papers /
    find_recent_papers if you are not certain of the exact topic name -
    those tools require an exact match (e.g. "Retrieval-Augmented
    Generation", not "RAG") and will return no results otherwise.
    """
    result = graph_service.list_topics(limit=limit)
    return _compact(result)


@tool
def find_topic_papers(topic: str, limit: int = 15, sort: str = "citations") -> str:
    """
    Get all indexed papers under an exact topic name. sort can be
    "citations" (most cited first), "year" (newest first), or "oldest"
    (earliest first). Call list_topics first if you're unsure of the
    exact topic name.
    """
    result = graph_service.topic_papers(topic, limit=limit, sort=sort)
    return _compact(result)


@tool
def find_foundational_papers(topic: str, limit: int = 5) -> str:
    """
    Get a heuristic set of "foundational" papers for a topic (high
    citation count, earlier publication year, within the indexed data).
    This is a proxy signal, not a verified historical claim - say so if
    you use this in your answer. Call list_topics first if unsure of the
    exact topic name.
    """
    result = graph_service.foundational_papers(topic, limit=limit)
    return _compact(result)


@tool
def find_recent_papers(topic: str, limit: int = 5) -> str:
    """
    Get the most recently published indexed papers for a topic. Useful
    for "what's new in X" or trend questions. Call list_topics first if
    unsure of the exact topic name.
    """
    result = graph_service.recent_papers(topic, limit=limit)
    return _compact(result)


@tool
def compare_papers(paper_ids: list[str]) -> str:
    """
    Compare 2-5 papers (by paper_id) on problem, method, architecture,
    dataset, evaluation, results, advantages, limitations, and research
    direction. Fields the papers' abstracts don't cover come back as
    "Not stated in the available abstract/metadata." rather than a
    guess - report that honestly rather than filling it in. Use
    search_papers first if you don't already have paper_ids to compare.
    """
    if len(paper_ids) < 2:
        return json.dumps({"error": "Need at least 2 paper_ids to compare."})
    if len(paper_ids) > 5:
        paper_ids = paper_ids[:5]
    try:
        result = comparison_service.compare_papers(paper_ids)
    except ValueError as e:
        return json.dumps({"error": str(e)})
    return _compact(result)


@tool
def build_reading_path(topic: str = "", paper_id: str = "", path_length: int = 8) -> str:
    """
    Build a foundational -> intermediate -> advanced -> recent reading
    path for a topic (or a paper's primary topic, if paper_id is given
    instead of topic). Use this for "what should I read to learn about
    X" or "give me a reading path on X" questions. Provide exactly one
    of topic or paper_id.
    """
    if not topic and not paper_id:
        return json.dumps({"error": "Provide either 'topic' or 'paper_id'."})
    try:
        result = reading_path_service.build_reading_path(
            topic=topic or None, paper_id=paper_id or None, path_length=path_length
        )
    except ValueError as e:
        return json.dumps({"error": str(e)})
    return _compact(result)


AGENT_TOOLS = [
    search_papers,
    find_citations,
    find_related_papers,
    find_citation_path,
    find_author,
    list_topics,
    find_topic_papers,
    find_foundational_papers,
    find_recent_papers,
    compare_papers,
    build_reading_path,
]
