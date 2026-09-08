"""
Thin, resilient client around the OpenAlex Works API.

OpenAlex is free and requires no API key. Supplying a contact email in
the User-Agent puts requests into OpenAlex's "polite pool", which gets
faster and more reliable rate limits.

Docs: https://docs.openalex.org/api-entities/works
"""
from __future__ import annotations

import httpx
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings

settings = get_settings()

PER_PAGE = 50  # OpenAlex max per page is 200, we keep it modest for a personal project


class OpenAlexClient:
    def __init__(self) -> None:
        self.base_url = settings.openalex_base_url
        self.headers = {
            "User-Agent": f"ResearchGraph/0.1 (mailto:{settings.openalex_polite_email})"
        }

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get(self, client: httpx.AsyncClient, url: str, params: dict) -> dict:
        resp = await client.get(url, params=params, headers=self.headers, timeout=30.0)
        resp.raise_for_status()
        return resp.json()

    async def search_works(
        self,
        topic: str,
        limit: int = 100,
        from_year: int | None = None,
    ) -> list[dict]:
        """
        Search OpenAlex "works" (papers) by free-text topic.

        Returns raw OpenAlex work dicts, capped at `limit` total results,
        paginating internally as needed.
        """
        results: list[dict] = []
        cursor = "*"

        filters = [f"default.search:{topic}"]
        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")

        async with httpx.AsyncClient() as client:
            while len(results) < limit:
                params = {
                    "search": topic,
                    "per_page": min(PER_PAGE, limit - len(results)),
                    "cursor": cursor,
                    "filter": ",".join(filters) if from_year else None,
                    "sort": "cited_by_count:desc",
                }
                params = {k: v for k, v in params.items() if v is not None}

                try:
                    data = await self._get(client, f"{self.base_url}/works", params)
                except httpx.HTTPStatusError as e:
                    logger.error(f"OpenAlex request failed: {e}")
                    break

                page_results = data.get("results", [])
                if not page_results:
                    break

                results.extend(page_results)
                cursor = data.get("meta", {}).get("next_cursor")
                if not cursor:
                    break

        logger.info(f"OpenAlex: fetched {len(results)} raw works for topic='{topic}'")
        return results[:limit]

    async def get_work_by_id(self, openalex_id: str) -> dict | None:
        """Fetch a single work by its OpenAlex ID (e.g. 'W2741809807')."""
        async with httpx.AsyncClient() as client:
            try:
                return await self._get(client, f"{self.base_url}/works/{openalex_id}", {})
            except httpx.HTTPStatusError as e:
                logger.error(f"Failed to fetch work {openalex_id}: {e}")
                return None
