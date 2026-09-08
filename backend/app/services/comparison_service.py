"""
Phase 5: structured paper comparison.

Reuses app.core.llm (Phase 3's raw-completion client) rather than the
agent's tool-calling model - this is a single prompt-in/JSON-out call,
not a multi-step tool loop, so the simpler client is the right fit.

The core anti-hallucination measure: the prompt gives the LLM ONLY each
paper's title + abstract + metadata (never its own trained knowledge of
the paper), and explicitly instructs it to say a field wasn't stated
rather than infer or recall it. This is the same "don't fill gaps with
assumed knowledge" rule from Phase 3's reasoning step, applied to a
narrower, more structured task.
"""
from __future__ import annotations

from loguru import logger

from app.core.llm import get_llm
from app.schemas.comparison import ComparisonResponse, PaperComparisonFields
from app.schemas.paper import PaperOut
from app.services import paper_service

SYSTEM_PROMPT = """You are comparing academic papers for a researcher. You are given each \
paper's title, abstract, and metadata - nothing else. You do not have access to the full \
paper text and must not use any trained/memorized knowledge about these papers, even if \
you recognize them.

For each paper, extract these fields STRICTLY from what is stated in its abstract/metadata:
problem, method, architecture, dataset, evaluation, results, advantages, limitations, \
research_direction.

If the abstract does not clearly state a field, you MUST use exactly this string for that \
field: "Not stated in the available abstract/metadata." Do not guess, infer beyond what's \
written, or fill gaps with what you recall about the paper from training - an abstract \
often omits architecture/dataset/results details that the full paper would cover, and \
guessing here is worse than admitting the gap.

Respond ONLY with a JSON object of this exact shape, no other text:
{
  "papers": {
    "<paper_id>": {
      "problem": "...", "method": "...", "architecture": "...", "dataset": "...",
      "evaluation": "...", "results": "...", "advantages": "...", "limitations": "...",
      "research_direction": "..."
    },
    ...
  },
  "comparison_summary": "<2-3 sentence summary of the key differences between these papers, citing paper_ids in brackets>"
}"""


def _format_paper_for_prompt(paper: dict) -> str:
    return (
        f"[{paper['paper_id']}] \"{paper['title']}\" ({paper.get('year', 'n.d.')})\n"
        f"Authors: {', '.join(paper.get('authors', [])) or 'unknown'}\n"
        f"Topics: {', '.join(paper.get('topics', [])) or 'none indexed'}\n"
        f"Abstract: {paper.get('abstract') or '(no abstract indexed for this paper)'}\n"
    )


def compare_papers(paper_ids: list[str]) -> ComparisonResponse:
    # 1. Fetch evidence - fail fast and clearly if any paper doesn't exist,
    # rather than silently comparing a partial set.
    papers: list[dict] = []
    missing: list[str] = []
    for pid in paper_ids:
        detail = paper_service.get_paper_detail(pid)
        if detail is None:
            missing.append(pid)
        else:
            papers.append(detail)

    if missing:
        raise ValueError(f"Paper(s) not found: {', '.join(missing)}")

    papers_out = [
        PaperOut(
            paper_id=p["paper_id"],
            title=p["title"],
            abstract=p.get("abstract"),
            authors=p.get("authors", []),
            year=p.get("year"),
            venue=p.get("venue"),
            doi=p.get("doi"),
            arxiv_id=p.get("arxiv_id"),
            topics=p.get("topics", []),
            cited_by_count=p.get("cited_by_count", 0) or 0,
        )
        for p in papers
    ]

    # 2. Prompt the LLM with ONLY that evidence
    user_prompt = "\n---\n".join(_format_paper_for_prompt(p) for p in papers)

    default_comparison = {p["paper_id"]: PaperComparisonFields() for p in papers}

    try:
        llm = get_llm()
        parsed = llm.complete_json(SYSTEM_PROMPT, user_prompt, max_tokens=2000)
        provider_name, model_name = llm.provider_name, llm.model_name
    except Exception as e:
        logger.error(f"Comparison LLM call failed (provider unset, no API key, or request error): {e}")
        parsed = None
        provider_name, model_name = "", ""

    if parsed is None:
        return ComparisonResponse(
            paper_ids=paper_ids,
            papers=papers_out,
            comparison=default_comparison,
            comparison_summary=(
                "LLM comparison is unavailable right now (no provider configured, or the call "
                "failed) - showing raw paper metadata only. See the 'papers' field for titles "
                "and abstracts to compare manually."
            ),
            llm_provider=provider_name,
            llm_model=model_name,
            degraded=True,
        )

    raw_comparison = parsed.get("papers", {})
    comparison: dict[str, PaperComparisonFields] = {}
    for p in papers:
        pid = p["paper_id"]
        fields = raw_comparison.get(pid)
        comparison[pid] = PaperComparisonFields(**fields) if fields else PaperComparisonFields()

    return ComparisonResponse(
        paper_ids=paper_ids,
        papers=papers_out,
        comparison=comparison,
        comparison_summary=parsed.get("comparison_summary", ""),
        llm_provider=provider_name,
        llm_model=model_name,
        degraded=False,
    )
