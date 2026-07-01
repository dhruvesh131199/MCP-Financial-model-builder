import { API_BASE } from "../api";

export interface SubChunk {
  id: string;
  parent_id: string;
  content: string;
  embedding: number[] | null;
}

export interface ParentChunk {
  id: string;
  ticker: string;
  year: number;
  doctype: string;
  chunk_index: number;
  item_id?: string | null;
  item_label?: string | null;
  content: string;
  char_count: number;
  approx_tokens: number;
  subchunks: SubChunk[];
}

export interface ChunkPlan {
  document_id: string;
  ticker: string;
  year: number;
  doctype: string;
  config: Record<string, number>;
  parent_chunks: ParentChunk[];
  parent_count: number;
  subchunk_count: number;
  warnings: string[];
}

export interface RagDocumentEntry {
  id: string;
  filing_key: string;
  document_id: string | null;
  ticker: string | null;
  year: number | null;
  doctype: string | null;
  label: string;
  source: string;
  status: "ready" | "error";
  error: string | null;
  from_cache: boolean;
  linked_at?: string;
  parent_count?: number;
  subchunk_count?: number;
}

export interface RagResolveResponse {
  success: boolean;
  from_cache: boolean;
  status: string;
  document_id: string | null;
  filing_key: string | null;
  rag_entry_id: string | null;
  label: string | null;
  ticker: string | null;
  year: number | null;
  doctype: string | null;
  source: string | null;
  parent_count: number;
  subchunk_count: number;
  error: string | null;
}

export async function fetchSessionRag(
  sessionId: string,
  ticker: string,
  fiscalYear?: number,
): Promise<RagResolveResponse> {
  const payload: { ticker: string; fiscal_year?: number } = { ticker };
  if (fiscalYear != null) payload.fiscal_year = fiscalYear;
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/rag/ingest/fetch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const body = (await res.json().catch(() => ({}))) as RagResolveResponse & {
    detail?: string;
  };
  if (!res.ok) {
    throw new Error(body.detail ?? body.error ?? `Fetch failed: ${res.status}`);
  }
  return body;
}

export async function uploadSessionRag(
  sessionId: string,
  file: File,
  meta: { ticker: string; year: number; doctype: string },
): Promise<RagResolveResponse> {
  const form = new FormData();
  form.append("file", file);
  form.append("ticker", meta.ticker.trim().toUpperCase());
  form.append("year", String(meta.year));
  form.append("doctype", meta.doctype);
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/rag/ingest/upload`, {
    method: "POST",
    body: form,
  });
  const body = (await res.json().catch(() => ({}))) as RagResolveResponse & {
    detail?: string;
  };
  if (!res.ok) {
    throw new Error(body.detail ?? body.error ?? `Upload failed: ${res.status}`);
  }
  return body;
}

export async function getSessionRagChunks(
  sessionId: string,
  documentId: string,
): Promise<ChunkPlan> {
  const res = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/rag/documents/${documentId}/chunks`,
  );
  if (!res.ok) {
    throw new Error(`Chunks load failed: ${res.status}`);
  }
  return res.json() as Promise<ChunkPlan>;
}
