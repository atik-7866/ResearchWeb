"""
Deduplication for normalized papers.

Two layers:
1. Exact dedup by paper_id (OpenAlex ID) - handles the same paper
   appearing twice across paginated API calls.
2. Fuzzy dedup by normalized title - handles the same paper being
   indexed slightly differently (e.g. preprint vs published version)
   which OpenAlex sometimes represents as separate records.
"""
from __future__ import annotations

import re

from loguru import logger

from app.schemas.paper import NormalizedPaper


def _title_key(title: str) -> str:
    """Lowercase, strip punctuation/whitespace so near-identical titles collide."""
    key = title.lower()
    key = re.sub(r"[^a-z0-9\s]", "", key)
    key = re.sub(r"\s+", " ", key).strip()
    return key


def deduplicate(papers: list[NormalizedPaper]) -> list[NormalizedPaper]:
    seen_ids: set[str] = set()
    seen_titles: set[str] = set()
    unique: list[NormalizedPaper] = []

    for paper in papers:
        if paper.paper_id in seen_ids:
            continue
        title_key = _title_key(paper.title)
        if title_key and title_key in seen_titles:
            continue

        seen_ids.add(paper.paper_id)
        if title_key:
            seen_titles.add(title_key)
        unique.append(paper)

    removed = len(papers) - len(unique)
    if removed:
        logger.info(f"Deduplication removed {removed} duplicate paper(s)")
    return unique
