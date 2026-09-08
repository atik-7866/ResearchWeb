from __future__ import annotations

from pydantic import BaseModel, Field, model_validator


class ReadingPathRequest(BaseModel):
    topic: str | None = Field(default=None, description="Topic to build a path for (fuzzy-matched against indexed topics)")
    paper_id: str | None = Field(default=None, description="Alternative anchor: use this paper's primary topic")
    path_length: int = Field(default=8, ge=4, le=16, description="Total papers across all 4 stages")

    @model_validator(mode="after")
    def _one_anchor_required(self):
        if not self.topic and not self.paper_id:
            raise ValueError("Provide either 'topic' or 'paper_id' to anchor the reading path.")
        return self


class ReadingPathStep(BaseModel):
    paper_id: str
    title: str
    year: int | None = None
    cited_by_count: int = 0
    stage: str = Field(description="foundational | intermediate | advanced | recent")
    reason: str = Field(description="Why this paper is placed here")
    relationship_to_previous: str = Field(description="How this paper connects to the one before it in the path")
    evidence: str = Field(description="The graph/citation fact backing the placement or relationship")


class ReadingPathResponse(BaseModel):
    anchor_topic: str
    steps: list[ReadingPathStep]
    narrative: str = Field(default="", description="Short LLM overview of the path, if an LLM is configured")
    llm_provider: str = ""
    llm_model: str = ""
    degraded: bool = Field(
        default=False,
        description="True if no LLM is configured - the path itself (stages, ordering, relationships) is graph-derived either way and unaffected.",
    )
    caveat: str = Field(
        default=(
            "Stage assignment (foundational/intermediate/advanced/recent) is a heuristic based on "
            "citation count and publication year within indexed papers, not a verified pedagogical "
            "ordering - use it as a starting point, not a syllabus."
        )
    )
