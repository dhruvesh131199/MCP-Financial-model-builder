import { API_BASE } from "../api";

export interface FinancialsFetchResult {
  ticker: string;
  success: boolean;
  file_id?: string;
  error?: string;
}

export interface FinancialsFetchResponse {
  request_id: string;
  tickers: string[];
  years: number[] | null;
  max_years: number | null;
  status: "success" | "partial" | "error";
  success_count: number;
  total_count: number;
  results: FinancialsFetchResult[];
  errors: string[];
  message?: string;
}

const inFlight = new Map<string, Promise<FinancialsFetchResponse>>();
const listeners = new Set<() => void>();

function notifyInFlightChanged(): void {
  listeners.forEach((listener) => listener());
}

function runSharedRequest(
  key: string,
  runner: () => Promise<FinancialsFetchResponse>,
): Promise<FinancialsFetchResponse> {
  const existing = inFlight.get(key);
  if (existing) return existing;
  const promise = runner().finally(() => {
    inFlight.delete(key);
    notifyInFlightChanged();
  });
  inFlight.set(key, promise);
  notifyInFlightChanged();
  return promise;
}

export function subscribeFinancialsInFlight(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function isFinancialsInFlight(sessionId: string): boolean {
  const prefix = `${sessionId}:`;
  for (const key of inFlight.keys()) {
    if (key.startsWith(prefix)) return true;
  }
  return false;
}

export async function fetchSessionFinancials(
  sessionId: string,
  body: { tickers: string[]; years?: number[]; max_years?: number },
): Promise<FinancialsFetchResponse> {
  const tickersKey = body.tickers.join(",");
  const yearsKey = body.years?.join(",") ?? "";
  const maxKey = body.max_years ?? "";
  const key = `${sessionId}:fetch:${tickersKey}:${yearsKey}:${maxKey}`;

  return runSharedRequest(key, async () => {
    const payload: { tickers: string[]; years?: number[]; max_years?: number } = {
      tickers: body.tickers,
    };
    if (body.years && body.years.length > 0) payload.years = body.years;
    if (body.max_years != null) payload.max_years = body.max_years;

    const res = await fetch(`${API_BASE}/api/sessions/${sessionId}/financials/fetch`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      keepalive: true,
    });
    const data = (await res.json().catch(() => ({}))) as FinancialsFetchResponse & {
      detail?: string;
    };
    if (!res.ok) {
      throw new Error(data.detail ?? `Fetch failed: ${res.status}`);
    }
    return data;
  });
}
