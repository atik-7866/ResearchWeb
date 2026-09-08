from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.schemas.paper import PaperSearchResponse
from app.services import paper_service

router = APIRouter(prefix="/papers", tags=["papers"])


@router.get("/search", response_model=PaperSearchResponse)
def search_papers(
    q: str = Query(..., min_length=2, description="Natural language search query"),
    top_k: int = Query(default=10, ge=1, le=50),
):
    """
    Phase 1: pure semantic (vector) search over ingested papers.
    Phase 4 will add /research/query for hybrid graph+vector search.
    """
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
