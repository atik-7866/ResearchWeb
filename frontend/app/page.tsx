"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, PaperOut, SystemStats } from "@/lib/api";

export default function HomePage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<PaperOut[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);

  useEffect(() => {
    api.getStats().then(setStats).catch(() => setStats(null));
  }, []);

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.searchPapers(query, 10);
      setResults(res.results);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Search failed. Is the backend running and has data been ingested?"
      );
      setResults([]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <header className="mb-10 text-center">
        <div className="mb-4 flex justify-center gap-2">
          <Link
            href="/research"
            className="rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
          >
            Hybrid RAG assistant →
          </Link>
          <Link
            href="/agent"
            className="rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
          >
            Research agent →
          </Link>
          <Link
            href="/compare"
            className="rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
          >
            Compare papers →
          </Link>
          <Link
            href="/reading-path"
            className="rounded-full border border-accent/40 bg-accent/10 px-4 py-1.5 text-xs font-medium text-accent hover:bg-accent/20"
          >
            Reading path →
          </Link>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">ResearchGraph</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Phase 1–6 — semantic search, graph traversal, Hybrid RAG, a
          tool-calling agent, paper comparison, and reading paths. Click a
          paper to explore the graph, or try one of the tools above.
        </p>
        {stats && (
          <p className="mt-3 text-xs text-neutral-500">
            {stats.papers_in_graph} papers indexed &middot; {stats.vectors_in_qdrant}{" "}
            vectors
          </p>
        )}
      </header>

      <form onSubmit={handleSearch} className="mb-8 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. retrieval augmented generation with knowledge graphs"
          className="flex-1 rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Searching…" : "Search"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      <div className="space-y-4">
        {results.map((paper) => (
          <Link
            href={`/papers/${paper.paper_id}`}
            key={paper.paper_id}
            className="block rounded-lg border border-border bg-surface p-4 transition hover:border-accent"
          >
            <div className="flex items-start justify-between gap-4">
              <h2 className="font-medium text-neutral-100">{paper.title}</h2>
              {paper.relevance_score != null && (
                <span className="shrink-0 rounded bg-accent/10 px-2 py-0.5 text-xs text-accent">
                  {(paper.relevance_score * 100).toFixed(0)}% match
                </span>
              )}
            </div>
            <p className="mt-1 text-xs text-neutral-500">
              {paper.authors.slice(0, 4).join(", ")}
              {paper.authors.length > 4 ? " et al." : ""} &middot; {paper.year ?? "n.d."}
              {paper.venue ? ` · ${paper.venue}` : ""}
            </p>
            {paper.abstract && (
              <p className="mt-2 line-clamp-3 text-sm text-neutral-400">
                {paper.abstract}
              </p>
            )}
            <div className="mt-2 flex flex-wrap gap-1">
              {paper.topics.slice(0, 5).map((t) => (
                <span
                  key={t}
                  className="rounded-full border border-border px-2 py-0.5 text-[11px] text-neutral-400"
                >
                  {t}
                </span>
              ))}
            </div>
          </Link>
        ))}

        {!loading && results.length === 0 && !error && (
          <p className="text-center text-sm text-neutral-600">
            No results yet. Ingest some papers first (see README), then search
            above.
          </p>
        )}
      </div>
    </main>
  );
}
