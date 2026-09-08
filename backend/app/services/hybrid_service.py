"""
Orchestrates the full Hybrid RAG pipeline for POST /research/query:

    Query Analyzer -> Vector Search + Graph Search -> Evidence Fusion -> LLM Reasoning -> Response

This is intentionally a thin coordinator - all the real logic lives in
app/rag/*.py (fusion, reasoning) and app/services/paper_service.py
(vector search). Keeping this file thin is what makes the Phase 4 agent
straightforward: the agent's tools call these same fusion/reasoning
functions rather than duplicating pipeline logic.
"""
from __future__ import annotations

from app.rag.evidence_fusion import fuse_evidence
from app.rag.llm_reasoning import reason_over_evidence
from app.schemas.research import GraphEvidenceOut, ResearchQueryResponse


def run_hybrid_query(query: str, vector_top_k: int = 8) -> ResearchQueryResponse:
    # Step 1 + 2: query analysis + vector/graph retrieval, fused into one bundle
    bundle = fuse_evidence(query, vector_top_k=vector_top_k)

    # Step 3: LLM reasons over the fused evidence
    reasoning = reason_over_evidence(bundle)

    graph_evidence_out = GraphEvidenceOut(
        citation_links_among_results=bundle.graph_evidence.citation_links_among_results,
        related_via_graph=bundle.graph_evidence.related_via_graph,
        topic_matches=bundle.graph_evidence.topic_matches,
    )

    return ResearchQueryResponse(
        query=query,
        answer=reasoning.answer,
        retrieved_facts=reasoning.retrieved_facts,
        interpretation=reasoning.interpretation,
        papers_cited=reasoning.papers_cited,
        topics_detected=bundle.topics_detected,
        vector_evidence=bundle.vector_evidence,
        graph_evidence=graph_evidence_out,
        llm_provider=reasoning.llm_provider,
        llm_model=reasoning.llm_model,
        degraded=reasoning.degraded,
    )
