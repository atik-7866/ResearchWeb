"""
LLM Reasoning: the third and final step of Hybrid RAG.

Takes the EvidenceBundle from evidence_fusion.py and asks the LLM to
answer the user's question using *only* that evidence, while explicitly
separating what was retrieved (fact) from what the model is inferring
(interpretation). This separation is enforced by the JSON schema we ask
for, not just requested in prose - the API response keeps them as
distinct fields so the frontend can render them differently (Phase 11 -
Explainability - builds directly on this).

If the LLM call fails (no API key configured, provider down) this
degrades to returning the raw evidence with a note - the hybrid retrieval
underneath still works and is inspectable even with zero LLM cost.
"""
from __future__ import annotations

from loguru import logger
from pydantic import BaseModel, Field

from app.core.llm import get_llm
from app.rag.evidence_fusion import EvidenceBundle

SYSTEM_PROMPT = """You are the reasoning layer of ResearchGraph, a hybrid graph + vector \
research assistant. You are given retrieved evidence from two sources:

1. VECTOR EVIDENCE: papers semantically similar to the user's query (from embedding search).
2. GRAPH EVIDENCE: structural relationships between papers - shared topics, \
shared authors, and actual citation links - from a knowledge graph.

Rules you must follow:
- Only use facts present in the evidence provided. Never invent paper titles, \
authors, years, or relationships not present in the evidence.
- If the evidence is insufficient to answer part of the question, say so explicitly \
rather than filling the gap with assumed knowledge.
- Explain BOTH why papers are semantically relevant AND how they are connected \
in the graph (citations, shared topics/authors) wherever graph evidence exists - \
this dual explanation is the whole point of hybrid retrieval.
- Reference papers by their paper_id in brackets, e.g. [W2741809807], so claims \
are traceable to evidence.
- Clearly separate "retrieved_facts" (directly stated in the evidence) from \
"interpretation" (your synthesis/reasoning connecting those facts).

Respond ONLY with a JSON object matching this exact shape, no other text:
{
  "answer": "<2-4 paragraph synthesized answer for the user, with [paper_id] citations>",
  "retrieved_facts": ["<short bullet-style fact directly from evidence>", ...],
  "interpretation": ["<short bullet-style inference/synthesis you are adding>", ...],
  "papers_cited": ["<paper_id>", ...]
}"""


class ReasoningResult(BaseModel):
    answer: str
    retrieved_facts: list[str] = Field(default_factory=list)
    interpretation: list[str] = Field(default_factory=list)
    papers_cited: list[str] = Field(default_factory=list)
    llm_provider: str = ""
    llm_model: str = ""
    degraded: bool = False  # true if the LLM call failed and this is a fallback


def _format_evidence_for_prompt(bundle: EvidenceBundle) -> str:
    lines = [f"USER QUERY: {bundle.query}\n"]

    lines.append("== VECTOR EVIDENCE (semantically similar papers) ==")
    for p in bundle.vector_evidence:
        lines.append(
            f"- [{p.paper_id}] \"{p.title}\" ({p.year or 'n.d.'}) - "
            f"match score {p.relevance_score}, {p.cited_by_count} citations. "
            f"Topics: {', '.join(p.topics[:4])}"
        )

    lines.append("\n== GRAPH EVIDENCE: citation links among the above papers ==")
    if bundle.graph_evidence.citation_links_among_results:
        for link in bundle.graph_evidence.citation_links_among_results:
            lines.append(
                f"- [{link['citing_id']}] \"{link['citing_title']}\" CITES "
                f"[{link['cited_id']}] \"{link['cited_title']}\""
            )
    else:
        lines.append("- None found among the retrieved papers.")

    lines.append("\n== GRAPH EVIDENCE: related papers per result (shared topics/authors) ==")
    if bundle.graph_evidence.related_via_graph:
        for paper_id, related in bundle.graph_evidence.related_via_graph.items():
            titles = "; ".join(f"[{r['paper_id']}] \"{r['title']}\"" for r in related[:3])
            lines.append(f"- Related to [{paper_id}]: {titles}")
    else:
        lines.append("- None found.")

    lines.append("\n== GRAPH EVIDENCE: detected topic context ==")
    if bundle.graph_evidence.topic_matches:
        for tm in bundle.graph_evidence.topic_matches:
            lines.append(f"- Topic \"{tm['topic']}\" ({tm['paper_count']} indexed papers)")
            for fp in tm["foundational_papers"]:
                lines.append(f"    foundational: [{fp['paper_id']}] \"{fp['title']}\" ({fp['year']})")
            for rp in tm["recent_papers"]:
                lines.append(f"    recent: [{rp['paper_id']}] \"{rp['title']}\" ({rp['year']})")
    else:
        lines.append("- No indexed topic matched this query closely.")

    return "\n".join(lines)


def reason_over_evidence(bundle: EvidenceBundle) -> ReasoningResult:
    try:
        llm = get_llm()
        user_prompt = _format_evidence_for_prompt(bundle)
        parsed = llm.complete_json(SYSTEM_PROMPT, user_prompt, max_tokens=1500)
        provider_name = llm.provider_name
        model_name = llm.model_name
    except Exception as e:
        logger.error(f"LLM call failed (provider unset, no API key, or request error): {e}")
        parsed = None
        provider_name = ""
        model_name = ""

    if parsed is None:
        return ReasoningResult(
            answer=(
                "The LLM reasoning step is unavailable right now (no provider configured, "
                "or the call failed) — showing raw retrieved evidence instead. See "
                "vector_evidence and graph_evidence in this response."
            ),
            llm_provider=provider_name,
            llm_model=model_name,
            degraded=True,
        )

    return ReasoningResult(
        answer=parsed.get("answer", ""),
        retrieved_facts=parsed.get("retrieved_facts", []),
        interpretation=parsed.get("interpretation", []),
        papers_cited=parsed.get("papers_cited", []),
        llm_provider=provider_name,
        llm_model=model_name,
        degraded=False,
    )
