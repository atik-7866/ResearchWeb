"""
Phase 6: personalized reading paths.

The path structure itself (which papers, in what stage, in what order)
is entirely graph-derived and requires no LLM - it's built from Phase 2's
existing find_foundational_papers/find_recent_papers/get_topic_papers
queries plus a simple year-based split for the middle two stages. This
matters because a reading path is exactly the kind of thing that should
NOT depend on an LLM's judgment of what's "foundational" - that's a
citation-graph fact, not an opinion.

An LLM is used only for the optional narrative polish (rephrasing the
per-paper "reason" and writing a short path overview) - if it's
unavailable, the path is still fully returned with template-based
reasons, just less prose-y. This mirrors Phases 3-5's degradation pattern,
but here "degraded" means "less polished," never "broken" or "empty."
"""
from __future__ import annotations

from loguru import logger

from app.core.llm import get_llm
from app.db.neo4j_client import get_neo4j_client
from app.rag.query_analyzer import detect_topics
from app.schemas.reading_path import ReadingPathResponse, ReadingPathStep
from app.services import paper_service

_STAGE_TEMPLATES = {
    "foundational": "Foundational paper on {topic} — {citations} citations suggests strong influence on later work in this area.",
    "intermediate": "An early-to-mid development in {topic}, published {year}, bridging the foundational work and more recent approaches.",
    "advanced": "A more developed approach within {topic}, published {year}, building on earlier ideas in the area.",
    "recent": "One of the more recently indexed papers on {topic} (published {year}) — useful for seeing where the area is heading.",
}


def _template_reason(paper: dict, stage: str, topic: str) -> str:
    template = _STAGE_TEMPLATES[stage]
    return template.format(
        topic=topic,
        citations=paper.get("cited_by_count", 0) or 0,
        year=paper.get("year", "n.d."),
    )


def _resolve_anchor_topic(topic: str | None, paper_id: str | None) -> str:
    if paper_id:
        detail = paper_service.get_paper_detail(paper_id)
        if not detail:
            raise ValueError(f"Paper '{paper_id}' not found")
        topics = detail.get("topics") or []
        if not topics:
            raise ValueError(f"Paper '{paper_id}' has no indexed topics to anchor a reading path on")
        return topics[0]

    assert topic is not None  # enforced by the request schema's validator
    matches = detect_topics(topic, max_topics=1)
    return matches[0].topic if matches else topic


def _build_path_steps(anchor_topic: str, path_length: int) -> list[tuple[dict, str]]:
    """Returns [(paper_dict, stage_name), ...] in reading order. Pure graph logic, no LLM."""
    neo4j = get_neo4j_client()
    per_stage = max(1, path_length // 4)

    foundational = neo4j.find_foundational_papers(anchor_topic, limit=per_stage)
    recent = neo4j.find_recent_papers(anchor_topic, limit=per_stage)

    used_ids = {p["paper_id"] for p in foundational} | {p["paper_id"] for p in recent}

    # Middle papers: everything else, sorted oldest-first, split at the
    # midpoint into "intermediate" (earlier half) and "advanced" (later
    # half), then within each half take the most-cited to prefer
    # influential papers over obscure ones at the same era.
    all_topic_papers = neo4j.get_topic_papers(anchor_topic, limit=300, sort="year")
    middle_pool = [p for p in all_topic_papers if p["paper_id"] not in used_ids and p.get("year") is not None]

    midpoint = len(middle_pool) // 2
    intermediate_candidates = middle_pool[:midpoint]
    advanced_candidates = middle_pool[midpoint:]

    intermediate = sorted(intermediate_candidates, key=lambda p: p.get("cited_by_count") or 0, reverse=True)[:per_stage]
    advanced = sorted(advanced_candidates, key=lambda p: p.get("cited_by_count") or 0, reverse=True)[:per_stage]

    ordered = (
        [(p, "foundational") for p in foundational]
        + [(p, "intermediate") for p in intermediate]
        + [(p, "advanced") for p in advanced]
        + [(p, "recent") for p in recent]
    )

    if not ordered:
        raise ValueError(f"No indexed papers found for topic '{anchor_topic}'")

    return ordered


def _link_steps(ordered: list[tuple[dict, str]], anchor_topic: str) -> list[ReadingPathStep]:
    """Fills in relationship_to_previous/evidence using actual citation edges between consecutive papers."""
    neo4j = get_neo4j_client()
    selected_ids = [p["paper_id"] for p, _ in ordered]
    edges = neo4j.get_citation_edges_among(selected_ids)
    citing_pairs = {(e["citing_id"], e["cited_id"]) for e in edges}

    steps: list[ReadingPathStep] = []
    for i, (paper, stage) in enumerate(ordered):
        reason = _template_reason(paper, stage, anchor_topic)

        if i == 0:
            relationship = "Starting point of the path."
            evidence = f"Selected as {stage}: {paper.get('cited_by_count', 0) or 0} citations, published {paper.get('year', 'n.d.')}."
        else:
            prev_id = ordered[i - 1][0]["paper_id"]
            this_id = paper["paper_id"]
            if (this_id, prev_id) in citing_pairs:
                relationship = "Cites the previous paper directly."
                evidence = "Direct citation edge found in the graph."
            elif (prev_id, this_id) in citing_pairs:
                relationship = "Is cited by the previous paper."
                evidence = "Direct citation edge found in the graph (reverse direction)."
            else:
                relationship = f"No direct citation link with the previous paper; grouped into the '{stage}' stage by year/citation count."
                evidence = f"{paper.get('cited_by_count', 0) or 0} citations, published {paper.get('year', 'n.d.')}."

        steps.append(
            ReadingPathStep(
                paper_id=paper["paper_id"],
                title=paper["title"],
                year=paper.get("year"),
                cited_by_count=paper.get("cited_by_count", 0) or 0,
                stage=stage,
                reason=reason,
                relationship_to_previous=relationship,
                evidence=evidence,
            )
        )
    return steps


_ENRICH_SYSTEM_PROMPT = """You are polishing a personalized reading path for a researcher. You are \
given a topic and an ordered list of papers with their stage (foundational/intermediate/advanced/recent), \
year, and citation count - no abstracts. Do not invent details about what the papers contain; work only \
from titles, stages, years, and citation counts.

For each paper, write ONE improved sentence explaining why it fits at that point in the path (you may \
lightly rephrase, but do not contradict the stage given).

Also write a 2-3 sentence overview of the path as a whole.

Respond ONLY with JSON of this exact shape:
{
  "per_paper": {"<paper_id>": "<one sentence>", ...},
  "narrative": "<2-3 sentence path overview>"
}"""


def _enrich_with_llm(steps: list[ReadingPathStep], anchor_topic: str) -> tuple[list[ReadingPathStep], str, str, str, bool]:
    """Best-effort LLM polish. Returns (steps, narrative, provider, model, degraded)."""
    listing = "\n".join(
        f"- [{s.paper_id}] \"{s.title}\" | stage={s.stage} | year={s.year or 'n.d.'} | citations={s.cited_by_count}"
        for s in steps
    )
    user_prompt = f"Topic: {anchor_topic}\n\n{listing}"

    try:
        llm = get_llm()
        parsed = llm.complete_json(_ENRICH_SYSTEM_PROMPT, user_prompt, max_tokens=1200)
        provider_name, model_name = llm.provider_name, llm.model_name
    except Exception as e:
        logger.error(f"Reading path LLM enrichment failed (provider unset, no API key, or request error): {e}")
        parsed = None
        provider_name, model_name = "", ""

    if parsed is None:
        return steps, "", provider_name, model_name, True

    per_paper = parsed.get("per_paper", {})
    for step in steps:
        if step.paper_id in per_paper and per_paper[step.paper_id]:
            step.reason = per_paper[step.paper_id]

    return steps, parsed.get("narrative", ""), provider_name, model_name, False


def build_reading_path(topic: str | None, paper_id: str | None, path_length: int = 8) -> ReadingPathResponse:
    anchor_topic = _resolve_anchor_topic(topic, paper_id)
    ordered = _build_path_steps(anchor_topic, path_length)
    steps = _link_steps(ordered, anchor_topic)

    steps, narrative, provider, model, degraded = _enrich_with_llm(steps, anchor_topic)

    return ReadingPathResponse(
        anchor_topic=anchor_topic,
        steps=steps,
        narrative=narrative,
        llm_provider=provider,
        llm_model=model,
        degraded=degraded,
    )
