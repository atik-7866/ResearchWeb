"""
ResearchGraph API - FastAPI entrypoint.

Phase 1 scope: health/stats, ingestion trigger, semantic search,
paper detail, and citation lookups. Later phases add routers under
app/api/routes/ for /research/* (hybrid query, compare, reading-path,
timeline, gap-analysis) and /library/* (personal PDF uploads) without
touching this file beyond one include_router line each.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from loguru import logger
from neo4j.exceptions import ServiceUnavailable
from qdrant_client.http.exceptions import ResponseHandlingException as QdrantUnavailable

from app.api.routes import agent, graph, papers, research, system
from app.config import get_settings
from app.db.neo4j_client import get_neo4j_client
from app.db.qdrant_client import get_qdrant_client

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"Starting {settings.app_name} ({settings.app_env})")
    # Warm up DB schema/collections on boot so the first request isn't slow/broken.
    try:
        get_neo4j_client().ensure_constraints()
        get_qdrant_client().ensure_collection()
    except Exception as e:
        logger.warning(f"Startup DB warm-up failed (will retry on first request): {e}")
    yield
    logger.info("Shutting down")
    get_neo4j_client().close()


app = FastAPI(
    title="ResearchGraph API",
    description="Hybrid Graph + Vector RAG research discovery platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router)
app.include_router(papers.router)
app.include_router(graph.router)
app.include_router(research.router)
app.include_router(agent.router)


@app.exception_handler(ServiceUnavailable)
async def neo4j_unavailable_handler(request: Request, exc: ServiceUnavailable):
    """
    Turn a raw Neo4j connection failure into a clean 503 instead of an
    unhandled 500 with a driver stack trace. Check /health first if you
    hit this.
    """
    logger.error(f"Neo4j unavailable while handling {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "Graph database is unavailable. Check /health and confirm Neo4j is running."},
    )


@app.exception_handler(QdrantUnavailable)
async def qdrant_unavailable_handler(request: Request, exc: QdrantUnavailable):
    """Same idea as the Neo4j handler above, for the vector store."""
    logger.error(f"Qdrant unavailable while handling {request.url.path}: {exc}")
    return JSONResponse(
        status_code=503,
        content={"detail": "Vector database is unavailable. Check /health and confirm Qdrant is running."},
    )


@app.get("/")
def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "phase": "Phase 6 - Personalized Reading Paths",
        "docs": "/docs",
    }
