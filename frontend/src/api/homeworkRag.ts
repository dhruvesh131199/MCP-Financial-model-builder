import { API_BASE } from "../api";

export interface ItemSection {
  item_id: string;
  title: string;
  label: string;
  char_count: number;
  approx_tokens: number;
  start_offset: number;
}

export interface SectionOutline {
  items: ItemSection[];
  preamble: ItemSection | null;
  total_chars: number;
  items_found: number;
  warnings: string[];
}

export interface RagIngestSummary {
  success: boolean;
  document_id: string;
  source: string;
  source_format: string;
  raw_filename: string;
  raw_bytes: number;
  markdown_chars: number;
  markdown_lines: number;
  filing?: {
    ticker?: string;
    entity_name?: string;
    accession_no?: string;
    filing_date?: string;
  } | null;
  narrative_checks?: Record<string, boolean>;
  section_outline?: SectionOutline | null;
  items_found?: number;
  parent_count?: number;
  subchunk_count?: number;
  report_url?: string;
  message?: string;
}

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

export interface RagDocumentDetail extends RagIngestSummary {
  markdown_excerpt: string;
  raw_url?: string;
  chunks_url?: string;
}

export async function fetchAnnualReportHomework(
  ticker: string,
  sessionId?: string,
): Promise<RagIngestSummary> {
  const res = await fetch(`${API_BASE}/api/homework/rag/ingest/fetch`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ticker, session_id: sessionId ?? null }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Fetch failed: ${res.status}`);
  }
  return res.json() as Promise<RagIngestSummary>;
}

export interface UploadMetadata {
  ticker: string;
  year: number;
  doctype: string;
  sessionId?: string;
}

export async function uploadDocumentHomework(
  file: File,
  meta: UploadMetadata,
): Promise<RagIngestSummary> {
  const form = new FormData();
  form.append("file", file);
  form.append("ticker", meta.ticker.trim().toUpperCase());
  form.append("year", String(meta.year));
  form.append("doctype", meta.doctype);
  if (meta.sessionId) form.append("session_id", meta.sessionId);
  const res = await fetch(`${API_BASE}/api/homework/rag/ingest/upload`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Upload failed: ${res.status}`);
  }
  return res.json() as Promise<RagIngestSummary>;
}

export async function getRagDocument(
  documentId: string,
  sessionId?: string,
): Promise<RagDocumentDetail> {
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const res = await fetch(`${API_BASE}/api/homework/rag/documents/${documentId}${q}`);
  if (!res.ok) {
    throw new Error(`Document load failed: ${res.status}`);
  }
  return res.json() as Promise<RagDocumentDetail>;
}

export async function getRagChunks(
  documentId: string,
  sessionId?: string,
): Promise<ChunkPlan> {
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  const res = await fetch(`${API_BASE}/api/homework/rag/documents/${documentId}/chunks${q}`);
  if (!res.ok) {
    throw new Error(`Chunks load failed: ${res.status}`);
  }
  return res.json() as Promise<ChunkPlan>;
}

export function ragReportUrl(documentId: string, sessionId?: string): string {
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return `${API_BASE}/api/homework/rag/documents/${documentId}/report${q}`;
}

export function ragRawUrl(documentId: string, sessionId?: string): string {
  const q = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : "";
  return `${API_BASE}/api/homework/rag/documents/${documentId}/raw${q}`;
}
