"use client";

import { useState } from "react";
import Link from "next/link";
import { api, ReadingPathResponse } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  foundational: "Foundational",
  intermediate: "Intermediate",
  advanced: "Advanced",
  recent: "Recent",
};

const STAGE_COLORS: Record<string, string> = {
  foundational: "border-l-blue-500",
  intermediate: "border-l-emerald-500",
  advanced: "border-l-amber-500",
  recent: "border-l-accent",
};

export default function ReadingPathPage() {
  const [topic, setTopic] = useState("");
  const [pathLength, setPathLength] = useState(8);
  const [result, setResult] = useState<ReadingPathResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.buildReadingPath({ topic, path_length: pathLength });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reading path generation failed");
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
        <h1 className="text-2xl font-semibold tracking-tight">Reading Path</h1>
        <p className="mt-2 max-w-2xl text-sm text-neutral-400">
          A foundational → intermediate → advanced → recent progression
          through a topic. The staging and ordering come entirely from the
          citation graph (citation count and publication year) — an LLM
          only polishes the wording if configured, it never decides the
          structure.
        </p>
      </header>

      <form onSubmit={handleGenerate} className="mb-8 flex flex-wrap gap-2">
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="e.g. Retrieval-Augmented Generation"
          className="flex-1 min-w-[240px] rounded-lg border border-border bg-surface px-4 py-3 text-sm outline-none focus:border-accent"
        />
        <select
          value={pathLength}
          onChange={(e) => setPathLength(Number(e.target.value))}
          className="rounded-lg border border-border bg-surface px-3 py-3 text-sm outline-none focus:border-accent"
        >
          <option value={4}>4 papers</option>
          <option value={8}>8 papers</option>
          <option value={12}>12 papers</option>
        </select>
        <button
          type="submit"
          disabled={loading}
          className="rounded-lg bg-accent px-5 py-3 text-sm font-medium text-white disabled:opacity-50"
        >
          {loading ? "Building…" : "Generate"}
        </button>
      </form>

      {error && (
        <div className="mb-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <p className="text-sm text-neutral-400">
            Path for <span className="text-neutral-200">{result.anchor_topic}</span>
          </p>

          {result.narrative && (
            <p className="rounded-lg border border-border bg-surface p-4 text-sm leading-relaxed text-neutral-300">
              {result.narrative}
            </p>
          )}

          <ol className="space-y-4">
            {result.steps.map((step, i) => (
              <li
                key={step.paper_id}
                className={`border-l-2 ${STAGE_COLORS[step.stage]} rounded-r-lg bg-surface p-4 pl-5`}
              >
                <div className="flex items-center gap-2">
                  <span className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                    {STAGE_LABELS[step.stage] ?? step.stage}
                  </span>
                  <span className="text-xs text-neutral-600">
                    · {step.year ?? "n.d."} · {step.cited_by_count} citations
                  </span>
                </div>
                <Link
                  href={`/papers/${step.paper_id}`}
                  className="mt-1 block text-sm font-medium text-neutral-200 hover:text-accent"
                >
                  {i + 1}. {step.title}
                </Link>
                <p className="mt-2 text-sm text-neutral-400">{step.reason}</p>
                <p className="mt-2 text-xs text-neutral-600">
                  <span className="font-medium">{step.relationship_to_previous}</span>{" "}
                  — {step.evidence}
                </p>
              </li>
            ))}
          </ol>

          <p className="text-xs text-neutral-600">{result.caveat}</p>
        </div>
      )}

      {!result && !loading && !error && (
        <p className="text-sm text-neutral-600">
          Enter a topic close to one you&apos;ve ingested (check{" "}
          <code>/graph/topics</code> for exact names, or just try something
          close — it fuzzy-matches).
        </p>
      )}
    </main>
  );
}
