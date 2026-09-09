"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, ComparisonResponse, PaperComparisonFields, PaperOut } from "@/lib/api";

const FIELD_ORDER: { key: keyof PaperComparisonFields; label: string }[] = [
  { key: "problem", label: "Problem" },
  { key: "method", label: "Method" },
  { key: "architecture", label: "Architecture" },
  { key: "dataset", label: "Dataset" },
  { key: "evaluation", label: "Evaluation" },
  { key: "results", label: "Results" },
  { key: "advantages", label: "Advantages" },
  { key: "limitations", label: "Limitations" },
  { key: "research_direction", label: "Research direction" },
];

const NOT_STATED = "Not stated in the available abstract/metadata.";

export default function ComparePage() {
  const [idsInput, setIdsInput] = useState("");
  const [selectedPapers, setSelectedPapers] = useState<PaperOut[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [suggestions, setSuggestions] = useState<PaperOut[]>([]);
  const [searching, setSearching] = useState(false);
  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const trimmedQuery = searchQuery.trim();
    if (trimmedQuery.length < 2 || selectedPapers.length >= 5) {
      setSuggestions([]);
      return;
    }

    let active = true;
    const timer = window.setTimeout(async () => {
      setSearching(true);
      try {
        const response = await api.searchPapers(trimmedQuery, 6);
        if (active) {
          setSuggestions(response.results.filter((paper) => !selectedPapers.some((selected) => selected.paper_id === paper.paper_id)));
        }
      } catch {
        if (active) setSuggestions([]);
      } finally {
        if (active) setSearching(false);
      }
    }, 300);

    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [searchQuery, selectedPapers]);

  function addPaper(paper: PaperOut) {
    if (selectedPapers.length >= 5 || selectedPapers.some((selected) => selected.paper_id === paper.paper_id)) return;
    setSelectedPapers((current) => [...current, paper]);
    setSearchQuery("");
    setSuggestions([]);
  }

  function removePaper(paperId: string) {
    setSelectedPapers((current) => current.filter((paper) => paper.paper_id !== paperId));
  }

  async function handleCompare(e: React.FormEvent) {
    e.preventDefault();
    const manualIds = idsInput
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const ids = [...new Set([...selectedPapers.map((paper) => paper.paper_id), ...manualIds])];

    if (ids.length < 2) {
      setError("Enter at least 2 paper IDs, comma-separated.");
      return;
    }
    if (ids.length > 5) {
      setError("Compare at most 5 papers at once.");
      return;
    }

    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.comparePapers(ids);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Comparison failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <Link href="/" className="text-sm text-accent">
        ← Back to search
      </Link>

      <header className="mt-4 mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Compare Papers</h1>
        <p className="mt-2 max-w-2xl text-sm text-neutral-400">
          Structured side-by-side comparison, generated strictly from each
          paper&apos;s indexed title and abstract. A cell reading &quot;not
          stated&quot; means the abstract didn&apos;t cover that detail —
          not that the LLM couldn&apos;t find anything to say.
        </p>
      </header>

      <section className="mb-8">
        <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-neutral-500">
          Find papers to compare
        </label>
        <div className="relative">
          <input
            value={searchQuery}
            onChange={(event) => setSearchQuery(event.target.value)}
            placeholder={selectedPapers.length >= 5 ? "Maximum 5 papers selected" : "Search by title or topic"}
            disabled={selectedPapers.length >= 5}
            className="w-full rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-accent disabled:opacity-50"
          />
          {suggestions.length > 0 && (
            <div className="absolute z-10 mt-1 w-full overflow-hidden rounded-lg border border-border bg-surface shadow-xl">
              {suggestions.map((paper) => (
                <button
                  type="button"
                  key={paper.paper_id}
                  onClick={() => addPaper(paper)}
                  className="block w-full border-b border-border px-4 py-3 text-left last:border-0 hover:bg-accent/10"
                >
                  <span className="block text-sm text-neutral-200">{paper.title}</span>
                  <span className="text-xs text-neutral-500">{paper.year ?? "n.d."}</span>
                </button>
              ))}
            </div>
          )}
        </div>
        {searching && <p className="mt-2 text-xs text-neutral-600">Searching…</p>}
        {selectedPapers.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {selectedPapers.map((paper) => (
              <button
                type="button"
                key={paper.paper_id}
                onClick={() => removePaper(paper.paper_id)}
                className="rounded-full border border-accent/50 bg-accent/10 px-3 py-1 text-xs text-accent hover:bg-accent/20"
                title="Remove paper"
              >
                {paper.title.length > 36 ? `${paper.title.slice(0, 36)}…` : paper.title} ×
              </button>
            ))}
          </div>
        )}
      </section>

      <form onSubmit={handleCompare} className="mb-8">
        <label className="mb-2 block text-xs font-medium uppercase tracking-wide text-neutral-500">
          Or paste paper IDs (2–5, comma-separated)
        </label>
        <div className="flex gap-2">
          <input
            value={idsInput}
            onChange={(e) => setIdsInput(e.target.value)}
            placeholder="W2741809807, W3005318505"
            className="flex-1 rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-accent"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
          >
            {loading ? "Comparing…" : "Compare"}
          </button>
        </div>
      </form>

      {error && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-8">
          {result.degraded && (
            <div className="rounded-lg border border-yellow-900 bg-yellow-950/30 px-4 py-3 text-sm text-yellow-300">
              LLM comparison is unavailable (no provider/API key configured)
              — showing raw paper metadata below instead of a structured
              breakdown.
            </div>
          )}

          <section className="flex flex-wrap gap-4">
            {result.papers.map((p) => (
              <Link
                key={p.paper_id}
                href={`/papers/${p.paper_id}`}
                className="flex-1 min-w-[220px] rounded-lg border border-border bg-surface p-4 hover:border-accent"
              >
                <p className="text-sm font-medium text-neutral-200">{p.title}</p>
                <p className="mt-1 text-xs text-neutral-500">
                  {p.authors.slice(0, 3).join(", ")} · {p.year ?? "n.d."} ·{" "}
                  {p.cited_by_count} citations
                </p>
              </Link>
            ))}
          </section>

          {!result.degraded && result.comparison_summary && (
            <section>
              <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-neutral-500">
                Summary
              </h2>
              <p className="text-sm leading-relaxed text-neutral-300">
                {result.comparison_summary}
              </p>
            </section>
          )}

          <section className="overflow-x-auto">
            <table className="w-full border-collapse text-sm">
              <thead>
                <tr>
                  <th className="border-b border-border px-3 py-2 text-left text-xs uppercase tracking-wide text-neutral-500">
                    Field
                  </th>
                  {result.papers.map((p) => (
                    <th
                      key={p.paper_id}
                      className="border-b border-border px-3 py-2 text-left text-xs font-medium text-neutral-300"
                    >
                      {p.title.length > 40 ? p.title.slice(0, 40) + "…" : p.title}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {FIELD_ORDER.map(({ key, label }) => (
                  <tr key={key}>
                    <td className="border-b border-border px-3 py-3 align-top text-xs font-medium uppercase tracking-wide text-neutral-500">
                      {label}
                    </td>
                    {result.paper_ids.map((pid) => {
                      const value = result.comparison[pid]?.[key] ?? NOT_STATED;
                      const isNotStated = value === NOT_STATED;
                      return (
                        <td
                          key={pid}
                          className={`border-b border-border px-3 py-3 align-top text-sm ${
                            isNotStated ? "italic text-neutral-600" : "text-neutral-300"
                          }`}
                        >
                          {value}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </section>

          <p className="text-xs text-neutral-600">{result.caveat}</p>
        </div>
      )}

      {!result && !loading && !error && (
        <p className="text-sm text-neutral-600">
          Find paper IDs on the search page (they appear in each paper&apos;s
          URL, e.g. <code>/papers/W2741809807</code>) and paste 2–5 of them
          above, comma-separated.
        </p>
      )}
    </main>
  );
}
