import type { DcfResult, ModelRecord, Workspace } from "./types";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

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

export type { DcfResult, ModelRecord, Workspace };
