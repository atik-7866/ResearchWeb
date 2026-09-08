from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.paper import PaperOut


class ComparisonRequest(BaseModel):
    paper_ids: list[str] = Field(..., min_length=2, max_length=5, description="2-5 paper IDs to compare")


class PaperComparisonFields(BaseModel):
    """
    One structured breakdown per paper. Every field defaults to a
    stated "not available" marker rather than being omitted, so the
    frontend can render a consistent table even when the LLM (or the
    degraded fallback) couldn't fill every cell - a blank cell and an
    "explicitly not stated" cell mean different things to a researcher.
    """

    problem: str = "Not stated in the available abstract/metadata."
    method: str = "Not stated in the available abstract/metadata."
    architecture: str = "Not stated in the available abstract/metadata."
    dataset: str = "Not stated in the available abstract/metadata."
    evaluation: str = "Not stated in the available abstract/metadata."
    results: str = "Not stated in the available abstract/metadata."
    advantages: str = "Not stated in the available abstract/metadata."
    limitations: str = "Not stated in the available abstract/metadata."
    research_direction: str = "Not stated in the available abstract/metadata."


class ComparisonResponse(BaseModel):
    paper_ids: list[str]
    papers: list[PaperOut] = Field(description="The raw retrieved metadata used as evidence - not LLM output.")
    comparison: dict[str, PaperComparisonFields] = Field(
        description="paper_id -> structured comparison fields, LLM-derived from title/abstract only."
    )
    comparison_summary: str = Field(default="", description="Short LLM synthesis of the key differences.")
    llm_provider: str = ""
    llm_model: str = ""
    degraded: bool = Field(
        default=False,
        description="True if the LLM step failed/is unconfigured - comparison fields will be the 'not stated' defaults.",
    )
    caveat: str = Field(
        default=(
            "Comparison fields are generated strictly from each paper's indexed title/abstract - "
            "not the full paper text. A field reading 'not stated' means the abstract didn't cover "
            "it, not that the paper lacks it."
        )
    )
