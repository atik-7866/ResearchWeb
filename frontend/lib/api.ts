/**
 * Thin, typed wrapper around the ResearchGraph FastAPI backend.
 * Every backend endpoint used by the UI should have a corresponding
 * typed function here - components should never call fetch() directly.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export interface PaperOut {
  paper_id: string;
  title: string;
  abstract?: string | null;
  authors: string[];
  year?: number | null;
  venue?: string | null;
  doi?: string | null;
  arxiv_id?: string | null;
  topics: string[];
  cited_by_count: number;
  relevance_score?: number | null;
}

export interface PaperSearchResponse {
  query: string;
  count: number;
  results: PaperOut[];
}

export interface SystemStats {
  papers_in_graph: number;
  vectors_in_qdrant: number;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`API error ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export interface PaperRef {
  paper_id: string;
  title: string;
  year?: number | null;
  cited_by_count?: number | null;
}

export interface RelatedPaper extends PaperRef {
  shared_topics: number;
  shared_authors: number;
  relatedness_score: number;
}

export interface SimilarPaper extends PaperOut {}

export interface CitationLink {
  citing_id: string;
  citing_title: string;
  cited_id: string;
  cited_title: string;
}

export interface TopicContext {
  topic: string;
  paper_count: number;
  overlap_score: number;
  foundational_papers: Record<string, unknown>[];
  recent_papers: Record<string, unknown>[];
}

export interface HybridQueryResponse {
  query: string;
  answer: string;
  retrieved_facts: string[];
  interpretation: string[];
  papers_cited: string[];
  topics_detected: string[];
  vector_evidence: PaperOut[];
  graph_evidence: {
    citation_links_among_results: CitationLink[];
    related_via_graph: Record<string, RelatedPaper[]>;
    topic_matches: TopicContext[];
  };
  llm_provider: string;
  llm_model: string;
  degraded: boolean;
  evidence_note: string;
}

export interface PaperDetail {
  paper_id: string;
  title: string;
  abstract?: string;
  authors: string[];
  topics: string[];
  year?: number;
  venue?: string;
  doi?: string;
  arxiv_id?: string;
  cited_by_count?: number;
  references: PaperRef[];
  cited_by: PaperRef[];
}

export interface AgentToolCall {
  tool: string;
  input: Record<string, unknown>;
  output_preview: string;
}

export interface AgentQueryResponse {
  query: string;
  answer: string;
  tool_calls: AgentToolCall[];
  tools_used: string[];
  degraded: boolean;
}

export interface PaperComparisonFields {
  problem: string;
  method: string;
  architecture: string;
  dataset: string;
  evaluation: string;
  results: string;
  advantages: string;
  limitations: string;
  research_direction: string;
}

export interface ComparisonResponse {
  paper_ids: string[];
  papers: PaperOut[];
  comparison: Record<string, PaperComparisonFields>;
  comparison_summary: string;
  llm_provider: string;
  llm_model: string;
  degraded: boolean;
  caveat: string;
}

export interface ReadingPathStep {
  paper_id: string;
  title: string;
  year?: number | null;
  cited_by_count: number;
  stage: "foundational" | "intermediate" | "advanced" | "recent";
  reason: string;
  relationship_to_previous: string;
  evidence: string;
}

export interface ReadingPathResponse {
  anchor_topic: string;
  steps: ReadingPathStep[];
  narrative: string;
  llm_provider: string;
  llm_model: string;
  degraded: boolean;
  caveat: string;
}

export const api = {
  searchPapers: (query: string, topK = 10) =>
    request<PaperSearchResponse>(
      `/papers/search?q=${encodeURIComponent(query)}&top_k=${topK}`
    ),

  getPaper: (paperId: string) => request<PaperDetail>(`/papers/${paperId}`),

  getPaperCitations: (paperId: string) =>
    request<{ references: PaperOut[]; cited_by: PaperOut[] }>(
      `/papers/${paperId}/citations`
    ),

  getSimilarPapers: (paperId: string, topK = 5) =>
    request<{ paper_id: string; results: SimilarPaper[]; similarity_threshold: number }>(
      `/papers/${paperId}/similar?top_k=${topK}`
    ),

  getStats: () => request<SystemStats>("/stats"),

  getRelatedPapers: (paperId: string, limit = 8) =>
    request<{ paper_id: string; count: number; results: RelatedPaper[]; explanation: string }>(
      `/graph/papers/${paperId}/related?limit=${limit}`
    ),

  getCitationChain: (paperId: string, depth = 2, direction: "outgoing" | "incoming" = "outgoing") =>
    request<{ paths: { hops: number; chain: PaperRef[] }[] }>(
      `/graph/papers/${paperId}/citation-chain?depth=${depth}&direction=${direction}`
    ),

  hybridQuery: (query: string, vectorTopK = 8) =>
    request<HybridQueryResponse>("/research/query", {
      method: "POST",
      body: JSON.stringify({ query, vector_top_k: vectorTopK }),
    }),

  agentQuery: (query: string) =>
    request<AgentQueryResponse>("/agent/query", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  comparePapers: (paperIds: string[]) =>
    request<ComparisonResponse>("/research/compare", {
      method: "POST",
      body: JSON.stringify({ paper_ids: paperIds }),
    }),

  buildReadingPath: (params: { topic?: string; paper_id?: string; path_length?: number }) =>
    request<ReadingPathResponse>("/research/reading-path", {
      method: "POST",
      body: JSON.stringify(params),
    }),

  getHealth: () => request<{ status: string; neo4j: string; qdrant: string }>("/health"),

  runIngestion: (topic: string, limit: number, fromYear?: number) =>
    request<Record<string, unknown>>("/ingestion/run", {
      method: "POST",
      body: JSON.stringify({ topic, limit, from_year: fromYear ?? null }),
    }),
};
