import { useEffect, useState } from "react";
import {
  fetchSessionFinancials,
  isFinancialsInFlight,
  subscribeFinancialsInFlight,
} from "../api/sessionFinancials";
import { DETAILED_ANALYSIS_DISCLAIMER } from "../utils/metricOrder";
import type { FinancialsFetchLogEntry } from "../types";
import ChipInput from "./ChipInput";
import { FILL_REQUIRED_MSG } from "../utils/hubFormValidation";

interface FetchFinancialsHubPanelProps {
  sessionId: string;
  fetchLog: FinancialsFetchLogEntry[];
  onRefresh: () => void;
}

function normalizeTicker(raw: string): string | null {
  const sym = raw.trim().toUpperCase();
  return sym ? sym : null;
}

function normalizeYear(raw: string): string | null {
  const n = parseInt(raw.trim(), 10);
  if (Number.isNaN(n) || n < 1990 || n > 2100) return null;
  return String(n);
}

function formatLogScope(entry: FinancialsFetchLogEntry): string {
  if (entry.years && entry.years.length > 0) {
    return `FY ${entry.years.join(", ")}`;
  }
  if (entry.max_years != null) {
    return `Last ${entry.max_years} fiscal year${entry.max_years === 1 ? "" : "s"}`;
  }
  return "Latest filing";
}

export default function FetchFinancialsHubPanel({
  sessionId,
  fetchLog,
  onRefresh,
}: FetchFinancialsHubPanelProps) {
  const [tickers, setTickers] = useState<string[]>([]);
  const [years, setYears] = useState<string[]>([]);
  const [lastNYears, setLastNYears] = useState("");
  const [loading, setLoading] = useState(() => isFinancialsInFlight(sessionId));
  const [banner, setBanner] = useState<string | null>(null);
  const [tickersError, setTickersError] = useState(false);

  const lastNDisabled = years.length > 0;

  useEffect(() => {
    const sync = () => setLoading(isFinancialsInFlight(sessionId));
    sync();
    return subscribeFinancialsInFlight(sync);
  }, [sessionId]);

  async function handleSubmit() {
    if (tickers.length === 0) {
      setTickersError(true);
      setBanner(FILL_REQUIRED_MSG);
      return;
    }
    setTickersError(false);
    setBanner(null);

    const fiscalYears = years.map((y) => parseInt(y, 10));
    const maxYears = lastNYears ? parseInt(lastNYears, 10) : undefined;

    try {
      const result = await fetchSessionFinancials(sessionId, {
        tickers,
        years: fiscalYears.length > 0 ? fiscalYears : undefined,
        max_years: fiscalYears.length > 0 ? undefined : maxYears,
      });

      if (result.status === "success") {
        setBanner(
          `Fetched ${result.success_count}/${result.total_count} ticker${result.total_count === 1 ? "" : "s"} successfully.`,
        );
      } else if (result.status === "partial") {
        setBanner(
          `Partial success: ${result.success_count}/${result.total_count} tickers fetched. Check request history for errors.`,
        );
      } else {
        setBanner(result.errors[0] ?? "Fetch failed for all tickers");
      }
      onRefresh();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Fetch failed");
      onRefresh();
    }
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="border-b border-[var(--border-soft)] bg-gradient-to-r from-white to-emerald-50/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900">Fetch Financials</h2>
          <span className="rounded bg-emerald-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
            SEC
          </span>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-relaxed text-gray-600">
          {DETAILED_ANALYSIS_DISCLAIMER}
        </p>
        <p className="mt-2 text-xs text-gray-500">
          In the future, a commercial data provider may replace raw EDGAR mapping.
        </p>
      </div>

      <div className="flex-1 space-y-6 p-4">
        <div className="max-w-xl space-y-4">
          <div>
            <label className="text-xs font-medium text-gray-700">Tickers (up to 5)</label>
            <div className="mt-1.5">
              <ChipInput
                values={tickers}
                onChange={(next) => {
                  setTickers(next);
                  if (tickersError && next.length > 0) setTickersError(false);
                }}
                maxItems={5}
                error={tickersError}
                normalize={normalizeTicker}
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-700">Fiscal years (optional, up to 10)</label>
            <div className="mt-1.5">
              <ChipInput
                values={years}
                onChange={setYears}
                maxItems={10}
                placeholder="Type a year and press enter"
                normalize={normalizeYear}
                disabled={loading}
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-gray-700">
              Last N fiscal years (optional)
            </label>
            <p className="mt-0.5 text-xs text-gray-500">
              Used only when no specific fiscal years are added above. Example: choose 5 to fetch
              the five most recent annual filings.
            </p>
            <select
              value={lastNYears}
              onChange={(e) => setLastNYears(e.target.value)}
              disabled={loading || lastNDisabled}
              className="mt-1.5 w-full max-w-xs rounded-lg border border-gray-200 px-3 py-2 text-sm disabled:bg-gray-50 disabled:text-gray-400"
            >
              <option value="">—</option>
              {Array.from({ length: 10 }, (_, i) => i + 1).map((n) => (
                <option key={n} value={String(n)}>
                  {n}
                </option>
              ))}
            </select>
            {lastNDisabled && (
              <p className="mt-1 text-xs text-gray-400">
                Disabled while specific fiscal years are set.
              </p>
            )}
          </div>

          <button
            type="button"
            disabled={loading}
            onClick={() => void handleSubmit()}
            className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50"
          >
            {loading ? "Fetching…" : "Fetch financials"}
          </button>
        </div>

        {banner && (
          <div
            className={`max-w-xl rounded-lg border px-4 py-3 text-sm ${
              banner.includes("failed") ||
              banner.includes("fill all") ||
              banner.toLowerCase().includes("error")
                ? "border-red-200 bg-red-50 text-red-700"
                : banner.includes("Partial")
                  ? "border-amber-200 bg-amber-50 text-amber-800"
                  : "border-emerald-200 bg-emerald-50 text-emerald-800"
            }`}
          >
            {banner}
          </div>
        )}

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Request history
          </h3>
          {fetchLog.length === 0 ? (
            <p className="mt-2 text-sm text-gray-400">Form submissions will appear here.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {fetchLog.map((entry) => (
                <li
                  key={entry.id}
                  className="rounded-lg border border-gray-200 bg-white px-3 py-2"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900">
                        {entry.tickers.join(", ")}
                      </p>
                      <p className="text-xs text-gray-500">{formatLogScope(entry)}</p>
                      {entry.created_at && (
                        <p className="font-mono text-[10px] text-gray-400">{entry.created_at}</p>
                      )}
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase ${
                        entry.status === "success"
                          ? "bg-green-100 text-green-800"
                          : entry.status === "partial"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-red-100 text-red-800"
                      }`}
                    >
                      {entry.status}
                    </span>
                  </div>
                  <ul className="mt-2 flex flex-wrap gap-1.5">
                    {(entry.results ?? []).map((r) => (
                      <li
                        key={`${entry.id}-${r.ticker}`}
                        className={`rounded-full px-2 py-0.5 text-[10px] font-medium ${
                          r.success
                            ? "bg-emerald-50 text-emerald-800"
                            : "bg-red-50 text-red-700"
                        }`}
                        title={r.error}
                      >
                        {r.ticker}
                        {r.success ? " ✓" : " ✗"}
                      </li>
                    ))}
                  </ul>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
