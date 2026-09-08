"use client";

import { useState } from "react";
import Link from "next/link";
import { api, HybridQueryResponse } from "@/lib/api";

export default function ResearchAssistantPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<HybridQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.hybridQuery(query, 8);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Query failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-accent">
        ← Back to search
      </Link>

      <header className="mt-4 mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">AI Research Assistant</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Hybrid Graph + Vector RAG: every answer below is grounded in
          papers retrieved by semantic search <em>and</em> relationships
          pulled from the citation graph — shown separately from the LLM&apos;s
          synthesis.
        </p>
      </header>

      <form onSubmit={handleAsk} className="mb-8 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. How are RAG and knowledge graphs connected?"
          className="flex-1 rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Thinking…" : "Ask"}
        </button>
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
              LLM reasoning is unavailable (no provider/API key configured) —
              showing raw retrieved evidence below instead of a synthesized answer.
            </div>
          )}

          <section>
            <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-neutral-500">
              Answer
              {result.llm_provider && (
                <span className="ml-2 normal-case text-neutral-600">
                  ({result.llm_provider} / {result.llm_model})
                </span>
              )}
            </h2>
            <p className="whitespace-pre-line text-sm leading-relaxed text-neutral-200">
              {result.answer}
            </p>
          </section>

          {(result.retrieved_facts.length > 0 || result.interpretation.length > 0) && (
            <section className="grid gap-6 sm:grid-cols-2">
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
                  Retrieved facts
                </h3>
                <ul className="space-y-1 text-sm text-neutral-300">
                  {result.retrieved_facts.map((f, i) => (
                    <li key={i} className="rounded-md border border-border px-3 py-1.5">
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
              <div>
                <h3 className="mb-2 text-xs font-medium uppercase tracking-wide text-neutral-500">
                  LLM interpretation
                </h3>
                <ul className="space-y-1 text-sm text-neutral-400">
                  {result.interpretation.map((f, i) => (
                    <li key={i} className="rounded-md border border-dashed border-border px-3 py-1.5">
                      {f}
                    </li>
                  ))}
                </ul>
              </div>
            </section>
          )}

          <section>
            <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-neutral-500">
              Vector evidence ({result.vector_evidence.length})
            </h2>
            <p className="mb-3 text-xs text-neutral-600">Semantically similar papers, from Qdrant.</p>
            <div className="space-y-2">
              {result.vector_evidence.map((p) => (
                <Link
                  key={p.paper_id}
                  href={`/papers/${p.paper_id}`}
                  className="block rounded-md border border-border px-3 py-2 text-sm hover:border-accent"
                >
                  <span className="text-neutral-200">{p.title}</span>
                  <span className="ml-2 text-xs text-neutral-500">
                    {p.year ?? "n.d."} · {((p.relevance_score ?? 0) * 100).toFixed(0)}% match
                  </span>
                </Link>
              ))}
            </div>
          </section>

          {result.graph_evidence.citation_links_among_results.length > 0 && (
            <section>
              <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-neutral-500">
                Citation links found among results
              </h2>
              <p className="mb-3 text-xs text-neutral-600">
                From Neo4j — where semantic similarity and graph structure agree.
              </p>
              <div className="space-y-2 text-sm text-neutral-300">
                {result.graph_evidence.citation_links_among_results.map((link, i) => (
                  <div key={i} className="rounded-md border border-border px-3 py-2">
                    <span className="text-neutral-200">{link.citing_title}</span>
                    <span className="mx-2 text-accent">cites</span>
                    <span className="text-neutral-200">{link.cited_title}</span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {result.topics_detected.length > 0 && (
            <section>
              <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-neutral-500">
                Topics detected in your query
              </h2>
              <div className="flex flex-wrap gap-1">
                {result.topics_detected.map((t) => (
                  <span
                    key={t}
                    className="rounded-full border border-border px-2 py-0.5 text-[11px] text-neutral-400"
                  >
                    {t}
                  </span>
                ))}
              </div>
            </section>
          )}
        </div>
      )}

      {!result && !loading && !error && (
        <p className="text-sm text-neutral-600">
          Ask a question about the papers you&apos;ve ingested — e.g. &quot;What
          are the main approaches to retrieval-augmented generation?&quot; or
          &quot;How do these papers relate to each other?&quot;
        </p>
      )}
    </main>
  );
}
