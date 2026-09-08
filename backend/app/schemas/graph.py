"""
Response shapes for Phase 2 graph traversal endpoints. Kept separate
from schemas/paper.py because these describe graph query results
(often partial/aggregated), not full Paper records.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class PaperRef(BaseModel):
    """A minimal paper reference returned inside graph query results."""
    paper_id: str
    title: str
    year: Optional[int] = None
    cited_by_count: Optional[int] = None


class RelatedPaper(PaperRef):
    shared_topics: int = 0
    shared_authors: int = 0
    relatedness_score: float = 0.0


class RelatedPapersResponse(BaseModel):
    paper_id: str
    count: int
    results: list[RelatedPaper]
    explanation: str = Field(
        default="Ranked by shared topics and shared authors with the source paper "
        "(shared authorship weighted higher than a shared topic tag)."
    )


class CitationChainSegment(BaseModel):
    hops: int
    chain: list[PaperRef]


class CitationChainResponse(BaseModel):
    paper_id: str
    direction: str
    depth: int
    paths: list[CitationChainSegment]


class CitationPathResponse(BaseModel):
    from_id: str
    to_id: str
    found: bool
    hops: Optional[int] = None
    chain: list[PaperRef] = Field(default_factory=list)


class TopicPapersResponse(BaseModel):
    topic: str
    label: str  # "foundational" | "recent" | "all"
    count: int
    results: list[PaperRef]
    caveat: Optional[str] = None


class TopicBridgeResult(BaseModel):
    a_id: str
    a_title: str
    b_id: str
    b_title: str


class PapersBetweenTopicsResponse(BaseModel):
    topic_a: str
    topic_b: str
    direct_overlap: list[PaperRef]
    citation_bridges: list[TopicBridgeResult]


class AuthorProfileResponse(BaseModel):
    name: str
    paper_count: int
    papers: list[PaperRef]
    topics: list[str]
    coauthors: list[str]


class TopicSummary(BaseModel):
    topic: str
    paper_count: int


class TopicsListResponse(BaseModel):
    count: int
    topics: list[TopicSummary]


class TopicOverviewResponse(BaseModel):
    topic: str
    papers_by_year: list[dict]
    top_authors: list[dict]
