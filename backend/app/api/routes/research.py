"""
Endpoints under /research: Hybrid RAG (Phase 3) and Paper Comparison
(Phase 5).

/research/query - fuses vector + graph evidence before an LLM answers,
the core differentiator claimed in the project's positioning. Phase 11's
evaluation will quantify how much this actually helps versus either
retrieval mode alone.

/research/compare - structured comparison of 2-5 papers, grounded
strictly in indexed title/abstract data (see comparison_service.py for
the anti-hallucination approach).

/research/reading-path - foundational -> intermediate -> advanced ->
recent progression anchored on a topic or paper, graph-derived (see
reading_path_service.py).
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.schemas.comparison import ComparisonRequest, ComparisonResponse
from app.schemas.reading_path import ReadingPathRequest, ReadingPathResponse
from app.schemas.research import ResearchQueryRequest, ResearchQueryResponse
from app.services import comparison_service, hybrid_service, reading_path_service

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/query", response_model=ResearchQueryResponse)
def hybrid_query(request: ResearchQueryRequest):
    try:
        return hybrid_service.run_hybrid_query(request.query, vector_top_k=request.vector_top_k)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Hybrid query failed: {e}")


@router.post("/compare", response_model=ComparisonResponse)
def compare_papers(request: ComparisonRequest):
    """
    Phase 5: structured comparison of 2-5 papers, grounded strictly in
    each paper's indexed title/abstract - see comparison_service.py for
    the anti-hallucination approach.
    """
    try:
        return comparison_service.compare_papers(request.paper_ids)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


@router.post("/reading-path", response_model=ReadingPathResponse)
def reading_path(request: ReadingPathRequest):
    """
    Phase 6: foundational -> intermediate -> advanced -> recent reading
    path, anchored on a topic or a paper's primary topic. The stage
    assignment and ordering are entirely graph-derived (see
    reading_path_service.py); an LLM only polishes the prose if configured.
    """
    try:
        return reading_path_service.build_reading_path(
            topic=request.topic, paper_id=request.paper_id, path_length=request.path_length
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Reading path generation failed: {e}")
