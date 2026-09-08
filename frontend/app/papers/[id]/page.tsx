"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { api, PaperDetail, PaperRef, RelatedPaper } from "@/lib/api";

function PaperLink({ paper }: { paper: PaperRef }) {
  return (
    <Link
      href={`/papers/${paper.paper_id}`}
      className="block rounded-md border border-border px-3 py-2 text-sm hover:border-accent"
    >
      <span className="text-neutral-200">{paper.title}</span>
      <span className="ml-2 text-xs text-neutral-500">
        {paper.year ?? "n.d."}
        {paper.cited_by_count != null ? ` · ${paper.cited_by_count} citations` : ""}
      </span>
    </Link>
  );
}

export default function PaperDetailPage() {
  const params = useParams<{ id: string }>();
  const paperId = params.id;

  const [paper, setPaper] = useState<PaperDetail | null>(null);
  const [related, setRelated] = useState<RelatedPaper[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!paperId) return;
    setLoading(true);
    setError(null);

    Promise.all([
      api.getPaper(paperId),
      api.getRelatedPapers(paperId, 8).catch(() => ({ results: [] as RelatedPaper[] })),
    ])
      .then(([paperData, relatedData]) => {
        setPaper(paperData);
        setRelated(relatedData.results);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load paper")
      )
      .finally(() => setLoading(false));
  }, [paperId]);

  if (loading) {
    return <main className="mx-auto max-w-3xl px-6 py-16 text-sm text-neutral-500">Loading…</main>;
  }

  if (error || !paper) {
    return (
      <main className="mx-auto max-w-3xl px-6 py-16">
        <Link href="/" className="text-sm text-accent">
          ← Back to search
        </Link>
        <div className="mt-6 rounded-lg border border-red-900 bg-red-950/40 px-4 py-3 text-sm text-red-300">
          {error ?? "Paper not found"}
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <Link href="/" className="text-sm text-accent">
        ← Back to search
      </Link>

      <h1 className="mt-4 text-2xl font-semibold tracking-tight">{paper.title}</h1>
      <p className="mt-2 text-sm text-neutral-400">
        {paper.authors.join(", ")} &middot; {paper.year ?? "n.d."}
        {paper.venue ? ` · ${paper.venue}` : ""}
        {paper.cited_by_count != null ? ` · ${paper.cited_by_count} citations` : ""}
      </p>

      <div className="mt-2 flex flex-wrap gap-2">
        {paper.doi && (
          <a
            href={`https://doi.org/${paper.doi}`}
            target="_blank"
            className="text-xs text-accent underline"
          >
            DOI
          </a>
        )}
        {paper.arxiv_id && (
          <a
            href={`https://arxiv.org/abs/${paper.arxiv_id}`}
            target="_blank"
            className="text-xs text-accent underline"
          >
            arXiv
          </a>
        )}
      </div>

      {paper.abstract && (
        <p className="mt-6 text-sm leading-relaxed text-neutral-300">{paper.abstract}</p>
      )}

      <div className="mt-4 flex flex-wrap gap-1">
        {paper.topics.map((t) => (
          <span
            key={t}
            className="rounded-full border border-border px-2 py-0.5 text-[11px] text-neutral-400"
          >
            {t}
          </span>
        ))}
      </div>

      {/* Graph-derived sections below - each one is a direct Neo4j traversal, not an LLM guess */}

      <section className="mt-10">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          References ({paper.references.length})
        </h2>
        <div className="space-y-2">
          {paper.references.length === 0 && (
            <p className="text-sm text-neutral-600">None indexed yet.</p>
          )}
          {paper.references.map((p) => (
            <PaperLink key={p.paper_id} paper={p} />
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-neutral-500">
          Cited by ({paper.cited_by.length})
        </h2>
        <div className="space-y-2">
          {paper.cited_by.length === 0 && (
            <p className="text-sm text-neutral-600">None indexed yet.</p>
          )}
          {paper.cited_by.map((p) => (
            <PaperLink key={p.paper_id} paper={p} />
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="mb-1 text-sm font-medium uppercase tracking-wide text-neutral-500">
          Related papers ({related.length})
        </h2>
        <p className="mb-3 text-xs text-neutral-600">
          Ranked by shared topics and co-authorship in the graph — not semantic similarity.
        </p>
        <div className="space-y-2">
          {related.length === 0 && (
            <p className="text-sm text-neutral-600">No related papers found yet.</p>
          )}
          {related.map((p) => (
            <div key={p.paper_id} className="flex items-center justify-between gap-3">
              <div className="flex-1">
                <PaperLink paper={p} />
              </div>
              <span className="shrink-0 text-[11px] text-neutral-600">
                {p.shared_topics} topic{p.shared_topics === 1 ? "" : "s"}
                {p.shared_authors > 0 ? `, ${p.shared_authors} author(s)` : ""}
              </span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}
