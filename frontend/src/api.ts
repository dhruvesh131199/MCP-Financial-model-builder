import type {
  DcfComputeResponse,
  DcfDraftDefaults,
  DcfDraftInputs,
  DcfDraftSummary,
  DcfResult,
  Workspace,
} from "./types";
import { PUBLIC_API_URL } from "./config/publicUrls";

export const API_BASE = import.meta.env.VITE_API_URL ?? PUBLIC_API_URL;

export interface DcfDraftPatchBody {
  base_revenue?: number | null;
  wacc?: number | null;
  terminal_growth?: number | null;
  net_debt?: number | null;
  shares_outstanding?: number | null;
  revenue_growth?: (number | null)[];
  ebitda_margin?: (number | null)[];
  tax_rate?: (number | null)[];
  capex_pct?: (number | null)[];
  nwc_pct?: (number | null)[];
  defaults?: DcfDraftDefaults;
}

export async function createSession(): Promise<{ session_id: string; view_url: string }> {
  const res = await fetch(`${API_BASE}/api/sessions`, { method: "POST" });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json() as Promise<{ session_id: string; view_url: string }>;
}

export async function fetchSessionWorkspace(
  sessionId: string,
): Promise<Workspace & { exists: boolean }> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}`);
  if (res.status === 404) {
    return {
      session_id: sessionId,
      updated_at: null,
      models: [],
      files: [],
      exists: false,
    };
  }
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  const data = (await res.json()) as Workspace;
  return { ...data, exists: true };
}

export async function markSessionGuideSeen(sessionId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/guide-seen`, {
    method: "POST",
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
}

export async function deleteSessionFile(
  sessionId: string,
  fileId: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/files/${fileId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Delete failed: ${res.status}`);
  }
}

export async function deleteSessionModel(
  sessionId: string,
  modelId: string,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/models/${modelId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Delete failed: ${res.status}`);
  }
}

export async function patchDcfDraft(
  sessionId: string,
  modelId: string,
  body: DcfDraftPatchBody,
): Promise<DcfDraftSummary> {
  const res = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/models/${modelId}/dcf-draft`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `PATCH failed: ${res.status}`);
  }
  return res.json() as Promise<DcfDraftSummary>;
}

export async function computeDcfDraft(
  sessionId: string,
  modelId: string,
): Promise<DcfComputeResponse> {
  const res = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/models/${modelId}/dcf-compute`,
    { method: "POST" },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Compute failed: ${res.status}`);
  }
  return res.json() as Promise<DcfComputeResponse>;
}

export async function previewDcfDraft(
  sessionId: string,
  modelId: string,
): Promise<DcfResult> {
  const res = await fetch(
    `${API_BASE}/api/sessions/${sessionId}/models/${modelId}/dcf-preview`,
    { method: "POST" },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail ?? `Preview failed: ${res.status}`);
  }
  return res.json() as Promise<DcfResult>;
}

export type { DcfComputeResponse, DcfDraftInputs, DcfDraftSummary, DcfResult, Workspace };
