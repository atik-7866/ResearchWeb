"""
Converts raw, messy OpenAlex "work" JSON into the clean internal
NormalizedPaper shape. All the OpenAlex-specific field-name knowledge
lives here and nowhere else in the codebase.
"""
from __future__ import annotations

from loguru import logger

from app.schemas.paper import Author, NormalizedPaper


def _reconstruct_abstract(inverted_index: dict | None) -> str | None:
    """
    OpenAlex stores abstracts as an "inverted index" (word -> [positions])
    for copyright reasons instead of plain text. We reconstruct the
    original text from it.
    """
    if not inverted_index:
        return None
    position_map: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_map[pos] = word
    if not position_map:
        return None
    ordered = [position_map[i] for i in sorted(position_map.keys())]
    return " ".join(ordered)


def _extract_arxiv_id(work: dict) -> str | None:
    for location in work.get("locations", []) or []:
        source = location.get("source") or {}
        landing = (location.get("landing_page_url") or "")
        if source.get("display_name", "").lower() == "arxiv" or "arxiv.org" in landing:
            # landing pages look like https://arxiv.org/abs/2005.11401
            if "arxiv.org/abs/" in landing:
                return landing.split("arxiv.org/abs/")[-1].strip("/")
    return None


def normalize_work(work: dict) -> NormalizedPaper | None:
    """
    Turn one raw OpenAlex work dict into a NormalizedPaper.
    Returns None if the work is missing an unrecoverable required field (title).
    """
    openalex_id = work.get("id", "").rsplit("/", 1)[-1]  # strip the URL prefix
    title = (work.get("title") or work.get("display_name") or "").strip()

    if not openalex_id or not title:
        logger.warning(f"Skipping work with missing id/title: {work.get('id')}")
        return None

    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

    authors: list[Author] = []
    for authorship in work.get("authorships", []) or []:
        a = authorship.get("author") or {}
        name = a.get("display_name")
        if name:
            authors.append(
                Author(
                    openalex_id=(a.get("id") or "").rsplit("/", 1)[-1] or None,
                    name=name,
                )
            )

    primary_location = work.get("primary_location") or {}
    venue = (primary_location.get("source") or {}).get("display_name")

    topics = [
        t["display_name"]
        for t in (work.get("topics") or [])
        if t.get("display_name")
    ][:8]  # cap to keep the graph tidy

    doi = work.get("doi")
    if doi:
        doi = doi.replace("https://doi.org/", "")

    referenced_works = [
        w.rsplit("/", 1)[-1] for w in (work.get("referenced_works") or [])
    ]

    return NormalizedPaper(
        paper_id=openalex_id,
        openalex_id=openalex_id,
        title=title,
        abstract=abstract,
        authors=authors,
        year=work.get("publication_year"),
        venue=venue,
        doi=doi,
        arxiv_id=_extract_arxiv_id(work),
        topics=topics,
        cited_by_count=work.get("cited_by_count", 0) or 0,
        referenced_works=referenced_works,
        source="openalex",
    )


def normalize_batch(raw_works: list[dict]) -> list[NormalizedPaper]:
    normalized = []
    for w in raw_works:
        n = normalize_work(w)
        if n:
            normalized.append(n)
    return normalized
