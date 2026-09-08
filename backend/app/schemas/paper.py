"""
Canonical data shapes for a "Paper" as it flows through ResearchGraph:

    OpenAlex raw JSON -> Normalizer -> NormalizedPaper -> (Neo4j write, Qdrant write)
                                                        -> PaperOut (API response)

Keeping one normalized internal shape means every downstream consumer
(graph writer, embedder, API) agrees on field names and types.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Author(BaseModel):
    openalex_id: Optional[str] = None
    name: str


class NormalizedPaper(BaseModel):
    """The internal, cleaned representation of a single paper."""

    paper_id: str = Field(..., description="Stable ID, derived from OpenAlex ID")
    title: str
    abstract: Optional[str] = None
    authors: list[Author] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    cited_by_count: int = 0
    referenced_works: list[str] = Field(
        default_factory=list, description="OpenAlex IDs of papers this paper cites"
    )
    openalex_id: str
    source: str = "openalex"

    def embedding_text(self) -> str:
        """Text that gets embedded: title + abstract."""
        abstract = self.abstract or ""
        return f"{self.title.strip()}\n\n{abstract.strip()}".strip()


class PaperOut(BaseModel):
    """What the API returns to the frontend for a single paper."""

    paper_id: str
    title: str
    abstract: Optional[str] = None
    authors: list[str] = Field(default_factory=list)
    year: Optional[int] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    topics: list[str] = Field(default_factory=list)
    cited_by_count: int = 0
    relevance_score: Optional[float] = Field(
        default=None, description="Set when returned from semantic search"
    )


class PaperSearchResponse(BaseModel):
    query: str
    count: int
    results: list[PaperOut]


class IngestionRequest(BaseModel):
    """Body for POST /ingestion/run"""

    topic: str = Field(..., description="Search term passed to OpenAlex, e.g. 'retrieval augmented generation'")
    limit: int = Field(default=100, ge=1, le=1000)
    from_year: Optional[int] = Field(default=None, description="Only include papers published >= this year")


class IngestionResponse(BaseModel):
    topic: str
    requested: int
    fetched: int
    normalized: int
    deduplicated: int
    written_to_neo4j: int
    written_to_qdrant: int
    skipped_missing_abstract: int
