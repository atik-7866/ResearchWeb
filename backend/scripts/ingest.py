"""
CLI wrapper around the ingestion pipeline.

Usage (run inside the backend directory with the project venv active):

    python -m scripts.ingest --topic "retrieval augmented generation" --limit 150
    python -m scripts.ingest --topic "knowledge graph embeddings" --limit 100 --from-year 2020

"""
import argparse
import asyncio

from app.config import get_settings
from app.ingestion.pipeline import run_ingestion


async def main():
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Ingest papers from OpenAlex into ResearchGraph")
    parser.add_argument("--topic", type=str, default=settings.ingest_default_topic)
    parser.add_argument("--limit", type=int, default=settings.ingest_default_limit)
    parser.add_argument("--from-year", type=int, default=None)
    args = parser.parse_args()

    result = await run_ingestion(topic=args.topic, limit=args.limit, from_year=args.from_year)
    print("\n--- Ingestion Summary ---")
    for field, value in result.model_dump().items():
        print(f"{field:28s}: {value}")


if __name__ == "__main__":
    asyncio.run(main())
