from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

from app.schemas.paper import PaperOut


class ResearchQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Natural language research question")
    vector_top_k: int = Field(default=8, ge=1, le=20)


class CitationLink(BaseModel):
    citing_id: str
    citing_title: str
    cited_id: str
    cited_title: str


class TopicContext(BaseModel):
    topic: str
    paper_count: int
    overlap_score: float
    foundational_papers: list[dict]
    recent_papers: list[dict]


class GraphEvidenceOut(BaseModel):
    citation_links_among_results: list[CitationLink]
    related_via_graph: dict[str, list[dict]]
    topic_matches: list[TopicContext]


class ResearchQueryResponse(BaseModel):
    query: str
    answer: str
    retrieved_facts: list[str]
    interpretation: list[str]
    papers_cited: list[str]
    topics_detected: list[str]
    vector_evidence: list[PaperOut]
    graph_evidence: GraphEvidenceOut
    llm_provider: str
    llm_model: str
    degraded: bool = Field(
        default=False,
        description="True if the LLM reasoning step failed and this response is raw evidence only",
    )
    evidence_note: str = Field(
        default=(
            "vector_evidence and graph_evidence are retrieved facts from Qdrant/Neo4j. "
            "'answer' is the LLM's synthesis over that evidence and may include interpretation - "
            "see retrieved_facts vs interpretation for the split."
        )
    )
