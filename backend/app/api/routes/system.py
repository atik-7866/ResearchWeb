from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db.neo4j_client import get_neo4j_client
from app.db.qdrant_client import get_qdrant_client
from app.ingestion.pipeline import run_ingestion
from app.schemas.paper import IngestionRequest, IngestionResponse

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check():
    neo4j = get_neo4j_client()
    qdrant = get_qdrant_client()

    neo4j_ok = neo4j.verify_connectivity()
    try:
        qdrant.ensure_collection()
        qdrant_ok = True
    except Exception:
        qdrant_ok = False

    return {
        "status": "ok" if (neo4j_ok and qdrant_ok) else "degraded",
        "neo4j": "up" if neo4j_ok else "down",
        "qdrant": "up" if qdrant_ok else "down",
    }


@router.get("/stats")
def stats():
    neo4j = get_neo4j_client()
    qdrant = get_qdrant_client()
    return {
        "papers_in_graph": neo4j.count_papers(),
        "vectors_in_qdrant": qdrant.count(),
    }


@router.post("/ingestion/run", response_model=IngestionResponse)
async def trigger_ingestion(request: IngestionRequest):
    """
    Runs the full ingestion pipeline synchronously (fine for a personal
    project with a few hundred papers at a time). For larger volumes this
    would move to a background task queue (e.g. Celery/RQ) - noted as a
    future improvement, not needed for Phase 1 scope.
    """
    try:
        return await run_ingestion(
            topic=request.topic, limit=request.limit, from_year=request.from_year
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
