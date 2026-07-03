import { API_BASE } from "../api";

export interface DcfCreateResponse {
  success: boolean;
  model_id: string;
  model_name: string;
  ticker?: string | null;
  projection_years: number;
  reference_years: number;
  prefilled: {
    base_revenue?: number | null;
    shares_outstanding?: number | null;
  };
  message?: string;
}

export interface ComparativeCreateResponse {
  success: boolean;
  model_id: string;
  model_name: string;
  fiscal_year_used: number;
  fiscal_year_note?: string | null;
  market_data_errors?: string[];
  message?: string;
}

const inFlight = new Map<string, Promise<DcfCreateResponse | ComparativeCreateResponse>>();
const listeners = new Set<() => void>();

function notifyInFlightChanged(): void {
  listeners.forEach((listener) => listener());
}

function runSharedRequest<T>(key: string, runner: () => Promise<T>): Promise<T> {
  const existing = inFlight.get(key);
  if (existing) return existing as Promise<T>;
  const promise = runner().finally(() => {
    inFlight.delete(key);
    notifyInFlightChanged();
  });
  inFlight.set(key, promise as Promise<DcfCreateResponse | ComparativeCreateResponse>);
  notifyInFlightChanged();
  return promise;
}

export function subscribeModelsInFlight(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function isModelsInFlight(sessionId: string): boolean {
  const prefix = `${sessionId}:`;
  for (const key of inFlight.keys()) {
    if (key.startsWith(prefix)) return true;
  }
  return false;
}

export async function createSessionDcfModel(
  sessionId: string,
  body: {
    name: string;
    projection_years: number;
    ticker?: string;
    base_revenue?: number;
  },
): Promise<DcfCreateResponse> {
  const tickerKey = body.ticker?.trim().toUpperCase() || "none";
  const baseKey = body.base_revenue ?? "";
  const key = `${sessionId}:dcf:${body.name}:${tickerKey}:${body.projection_years}:${baseKey}`;

  return runSharedRequest(key, async () => {
    const payload: {
      name: string;
      projection_years: number;
      ticker?: string;
      base_revenue?: number;
    } = {
      name: body.name.trim(),
      projection_years: body.projection_years,
    };
    if (body.ticker?.trim()) payload.ticker = body.ticker.trim().toUpperCase();
    if (body.base_revenue != null) payload.base_revenue = body.base_revenue;

    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/models/dcf`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    const data = (await res.json().catch(() => ({}))) as DcfCreateResponse & {
      detail?: string;
    };
    if (!res.ok) {
      throw new Error(data.detail ?? `Create failed: ${res.status}`);
    }
    return data;
  });
}

export async function createSessionComparativeModel(
  sessionId: string,
  body: {
    name?: string;
    target: string;
    peers: string[];
  },
): Promise<ComparativeCreateResponse> {
  const nameKey = body.name?.trim() || "default";
  const peersKey = body.peers.join(",");
  const key = `${sessionId}:comps:${nameKey}:${body.target}:${peersKey}`;

  return runSharedRequest(key, async () => {
    const payload: { name?: string; target: string; peers: string[] } = {
      target: body.target.trim(),
      peers: body.peers.map((p) => p.trim()).filter(Boolean),
    };
    if (body.name?.trim()) payload.name = body.name.trim();

    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/models/comparative`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    const data = (await res.json().catch(() => ({}))) as ComparativeCreateResponse & {
      detail?: string;
    };
    if (!res.ok) {
      throw new Error(data.detail ?? `Create failed: ${res.status}`);
    }
    return data;
  });
}
