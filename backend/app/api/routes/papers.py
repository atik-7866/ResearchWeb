from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.ingestion.pipeline import run_ingestion
from app.schemas.paper import PaperSearchResponse
from app.services import paper_service

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/search", response_model=PaperSearchResponse)
async def search_papers(
    q: str = Query(..., min_length=2, description="Natural language search query"),
    top_k: int = Query(default=10, ge=1, le=50),
):
    """
    Fetch and index papers for the query, then run semantic search over them.

    Upserts are idempotent, so repeated searches enrich the existing index
    without requiring a separate ingestion step from the user.
    """
    await run_ingestion(topic=q, limit=max(top_k, 10))
    results = paper_service.semantic_search(q, top_k=top_k)
    return PaperSearchResponse(query=q, count=len(results), results=results)


@router.get("/{paper_id}")
def get_paper(paper_id: str):
    paper = paper_service.get_paper_detail(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    return paper


@router.get("/{paper_id}/citations")
def get_paper_citations(paper_id: str):
    result = paper_service.get_paper_citations(paper_id)
    if not result["references"] and not result["cited_by"]:
        # Not necessarily an error - the paper might just have no known
        # in-graph citations - but confirm the paper itself exists.
        if not paper_service.get_paper_detail(paper_id):
            raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    return result


@router.get("/{paper_id}/similar")
def get_similar_papers(
    paper_id: str,
    top_k: int = Query(default=5, ge=1, le=20),
):
    """Return indexed papers with highly similar semantic content."""
    if not paper_service.get_paper_detail(paper_id):
        raise HTTPException(status_code=404, detail=f"Paper '{paper_id}' not found")
    return {
        "paper_id": paper_id,
        "results": paper_service.find_similar_papers(paper_id, top_k=top_k),
        "similarity_threshold": 0.80,
    }
