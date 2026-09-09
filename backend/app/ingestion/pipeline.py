"""
Reusable ingestion pipeline:

    OpenAlex --fetch--> raw dicts
             --normalize--> NormalizedPaper[]
             --deduplicate--> NormalizedPaper[]
             --embed--> vectors
             --write--> Neo4j (graph) + Qdrant (vectors)

This is called both by the CLI script (scripts/ingest.py) and the
POST /ingestion/run API endpoint, so there is exactly one ingestion
code path.
"""
from __future__ import annotations

from loguru import logger

from app.core.embeddings import get_embedder
from app.db.neo4j_client import get_neo4j_client
from app.db.qdrant_client import get_qdrant_client
from app.ingestion.dedup import deduplicate
from app.ingestion.normalizer import normalize_batch
from app.ingestion.openalex_client import OpenAlexClient
from app.schemas.paper import IngestionResponse, NormalizedPaper


async def run_ingestion(topic: str, limit: int, from_year: int | None = None) -> IngestionResponse:
    logger.info(f"Starting ingestion: topic='{topic}' limit={limit} from_year={from_year}")

    # 1. Fetch
    client = OpenAlexClient()
    raw_works = await client.search_works(topic=topic, limit=limit, from_year=from_year)

    # 2. Normalize
    normalized = normalize_batch(raw_works)

    # 3. Deduplicate
    unique_papers = deduplicate(normalized)

    # 4. Titles are still useful search content when an abstract is absent.
    embeddable: list[NormalizedPaper] = unique_papers
    skipped = 0

    # 5. Embed
    embedder = get_embedder()
    neo4j = get_neo4j_client()
    qdrant = get_qdrant_client()
    qdrant.ensure_collection()
    neo4j.ensure_constraints()

    written_neo4j = 0
    written_qdrant = 0

    if embeddable:
        texts = [p.embedding_text() for p in embeddable]
        vectors = embedder.embed(texts)

        for paper, vector in zip(embeddable, vectors):
            # 6. Write to graph
            neo4j.upsert_paper(paper)
            written_neo4j += 1
            # 7. Write to vector store
            qdrant.upsert_paper(paper, vector)
            written_qdrant += 1

        # Second pass: citation edges, once all paper nodes in this batch exist
        for paper in embeddable:
            neo4j.upsert_citations(paper)

    logger.info(
        f"Ingestion complete: fetched={len(raw_works)} normalized={len(normalized)} "
        f"unique={len(unique_papers)} written_neo4j={written_neo4j} written_qdrant={written_qdrant}"
    )

    return IngestionResponse(
        topic=topic,
        requested=limit,
        fetched=len(raw_works),
        normalized=len(normalized),
        deduplicated=len(unique_papers),
        written_to_neo4j=written_neo4j,
        written_to_qdrant=written_qdrant,
        skipped_missing_abstract=skipped,
    )
