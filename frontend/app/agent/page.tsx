"use client";

import { useState } from "react";
import Link from "next/link";
import { api, AgentQueryResponse } from "@/lib/api";

export default function AgentPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<AgentQueryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.agentQuery(query);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent query failed");
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
        <h1 className="text-2xl font-semibold tracking-tight">Research Agent</h1>
        <p className="mt-2 text-sm text-neutral-400">
          Unlike the <Link href="/research" className="text-accent underline">Hybrid RAG assistant</Link>,
          which always runs the same vector+graph pipeline, this agent{" "}
          <em>decides for itself</em> which tools to call and how many steps
          to take — a simple lookup might take one call, an open-ended
          question might take several. Every tool call it makes is shown
          below, in order.
        </p>
      </header>

      <form onSubmit={handleAsk} className="mb-8 flex gap-2">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="e.g. How has RAG research evolved over time?"
          className="flex-1 rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Working…" : "Ask"}
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
              {result.answer}
            </div>
          )}

          {!result.degraded && (
            <>
              <section>
                <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-neutral-500">
                  Answer
                </h2>
                <p className="whitespace-pre-line text-sm leading-relaxed text-neutral-200">
                  {result.answer}
                </p>
              </section>

              <section>
                <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-neutral-500">
                  Tool calls ({result.tool_calls.length})
                </h2>
                <p className="mb-3 text-xs text-neutral-600">
                  The agent chose these tools itself, in this order —
                  nothing here was forced by a fixed pipeline.
                </p>
                <ol className="space-y-3">
                  {result.tool_calls.map((tc, i) => (
                    <li key={i} className="rounded-lg border border-border p-3">
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent">
                          {i + 1}
                        </span>
                        <code className="text-sm text-neutral-200">{tc.tool}</code>
                        <code className="text-xs text-neutral-500">
                          {JSON.stringify(tc.input)}
                        </code>
                      </div>
                      <pre className="mt-2 overflow-x-auto whitespace-pre-wrap text-xs text-neutral-500">
                        {tc.output_preview}
                      </pre>
                    </li>
                  ))}
                  {result.tool_calls.length === 0 && (
                    <p className="text-sm text-neutral-600">
                      The agent answered directly without calling any tools.
                    </p>
                  )}
                </ol>
              </section>
            </>
          )}
        </div>
      )}

      {!result && !loading && !error && (
        <p className="text-sm text-neutral-600">
          Try something that needs multiple steps, like &quot;How has RAG
          research evolved?&quot; or &quot;What has [an author in your
          library] published recently?&quot;
        </p>
      )}
    </main>
  );
}
