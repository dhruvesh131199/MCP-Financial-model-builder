import { useEffect, useState } from "react";
import {
  createSessionComparativeModel,
  createSessionDcfModel,
  isModelsInFlight,
  subscribeModelsInFlight,
} from "../api/sessionModels";
import {
  FILL_REQUIRED_MSG,
  inputFieldClass,
} from "../utils/hubFormValidation";
import ChipInput from "./ChipInput";

type ModelTab = "dcf" | "comparative";

interface ModelsHubPanelProps {
  sessionId: string;
  onRefresh: () => void;
  onCreated: (modelId: string) => void;
}

type DcfFieldErrors = {
  name: boolean;
  years: boolean;
  baseRevenue: boolean;
};

type ComparativeFieldErrors = {
  target: boolean;
  peers: boolean;
};

const EMPTY_DCF_ERRORS: DcfFieldErrors = { name: false, years: false, baseRevenue: false };
const EMPTY_COMP_ERRORS: ComparativeFieldErrors = { target: false, peers: false };

function parseNum(raw: string): number | null {
  const trimmed = raw.trim();
  if (!trimmed) return null;
  const n = Number(trimmed);
  return Number.isNaN(n) ? null : n;
}

function normalizeTicker(raw: string): string | null {
  const sym = raw.trim().toUpperCase();
  return sym ? sym : null;
}

function isErrorBanner(banner: string): boolean {
  return (
    banner.toLowerCase().includes("fail") ||
    banner.includes("required") ||
    banner.includes("valid") ||
    banner.includes("not found") ||
    banner.includes("SEC fetch") ||
    banner.includes("fill all")
  );
}

export default function ModelsHubPanel({
  sessionId,
  onRefresh,
  onCreated,
}: ModelsHubPanelProps) {
  const [tab, setTab] = useState<ModelTab>("dcf");
  const [modelName, setModelName] = useState("");
  const [ticker, setTicker] = useState("");
  const [projectionYears, setProjectionYears] = useState("5");
  const [baseRevenue, setBaseRevenue] = useState("");
  const [compName, setCompName] = useState("");
  const [compTarget, setCompTarget] = useState("");
  const [compPeers, setCompPeers] = useState<string[]>([]);
  const [dcfErrors, setDcfErrors] = useState<DcfFieldErrors>(EMPTY_DCF_ERRORS);
  const [compErrors, setCompErrors] = useState<ComparativeFieldErrors>(EMPTY_COMP_ERRORS);
  const [loading, setLoading] = useState(() => isModelsInFlight(sessionId));
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setLoading(isModelsInFlight(sessionId));
    sync();
    return subscribeModelsInFlight(sync);
  }, [sessionId]);

  function clearDcfBanner() {
    setBanner(null);
    setDcfErrors(EMPTY_DCF_ERRORS);
  }

  function clearCompBanner() {
    setBanner(null);
    setCompErrors(EMPTY_COMP_ERRORS);
  }

  async function handleCreateDcf() {
    const name = modelName.trim();
    const years = parseInt(projectionYears, 10);
    const baseRev = baseRevenue.trim() ? parseNum(baseRevenue) : undefined;
    const errors: DcfFieldErrors = {
      name: !name,
      years: Number.isNaN(years) || years < 1 || years > 10,
      baseRevenue: Boolean(baseRevenue.trim() && baseRev == null),
    };

    if (errors.name || errors.years) {
      setDcfErrors(errors);
      setBanner(FILL_REQUIRED_MSG);
      return;
    }
    if (errors.baseRevenue) {
      setDcfErrors(errors);
      setBanner("Enter a valid base revenue in $M or leave blank");
      return;
    }

    setDcfErrors(EMPTY_DCF_ERRORS);
    setBanner(null);
    try {
      const result = await createSessionDcfModel(sessionId, {
        name,
        projection_years: years,
        ticker: ticker.trim().toUpperCase() || undefined,
        base_revenue: baseRev ?? undefined,
      });
      setBanner(result.message ?? `Created ${result.model_name}`);
      onRefresh();
      onCreated(result.model_id);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Create failed");
      onRefresh();
    }
  }

  async function handleCreateComparative() {
    const target = compTarget.trim().toUpperCase();
    const errors: ComparativeFieldErrors = {
      target: !target,
      peers: compPeers.length === 0,
    };

    if (errors.target || errors.peers) {
      setCompErrors(errors);
      setBanner(FILL_REQUIRED_MSG);
      return;
    }

    setCompErrors(EMPTY_COMP_ERRORS);
    setBanner(null);
    try {
      const result = await createSessionComparativeModel(sessionId, {
        name: compName.trim() || undefined,
        target,
        peers: compPeers,
      });
      setBanner(result.message ?? `Created ${result.model_name}`);
      onRefresh();
      onCreated(result.model_id);
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Comparative analysis failed");
      onRefresh();
    }
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="border-b border-[var(--border-soft)] bg-gradient-to-r from-white to-violet-50/50 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900">Create a model</h2>
          <span className="rounded bg-violet-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
            Models
          </span>
        </div>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-gray-600">
          Build valuation templates from the dashboard. DCF and comparative models use the same
          engines as chat — SEC data is fetched automatically when you run comparative analysis.
        </p>
      </div>

      <div className="flex-1 space-y-6 p-4">
        <div className="flex rounded-lg border border-gray-200 p-0.5 text-xs w-fit">
          <button
            type="button"
            onClick={() => {
              setTab("dcf");
              clearDcfBanner();
            }}
            className={`rounded-md px-3 py-1.5 font-medium ${
              tab === "dcf" ? "bg-violet-600 text-white" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            DCF model
          </button>
          <button
            type="button"
            onClick={() => {
              setTab("comparative");
              clearCompBanner();
            }}
            className={`rounded-md px-3 py-1.5 font-medium ${
              tab === "comparative"
                ? "bg-violet-600 text-white"
                : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            Comparative model
          </button>
        </div>

        {tab === "dcf" && (
          <div className="max-w-lg space-y-4">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-700">Model name</span>
              <input
                type="text"
                value={modelName}
                onChange={(e) => {
                  setModelName(e.target.value);
                  if (dcfErrors.name) setDcfErrors((prev) => ({ ...prev, name: false }));
                }}
                className={inputFieldClass(dcfErrors.name)}
                placeholder="e.g. Apple 5Y DCF"
                disabled={loading}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-700">
                Ticker <span className="font-normal text-gray-400">(optional)</span>
              </span>
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value)}
                className={inputFieldClass(false)}
                placeholder="e.g. aapl"
                disabled={loading}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-700">Projection years</span>
              <input
                type="number"
                min={1}
                max={10}
                value={projectionYears}
                onChange={(e) => {
                  setProjectionYears(e.target.value);
                  if (dcfErrors.years) setDcfErrors((prev) => ({ ...prev, years: false }));
                }}
                className={inputFieldClass(dcfErrors.years, "w-28")}
                disabled={loading}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-700">Base revenue ($M)</span>
              <input
                type="text"
                inputMode="decimal"
                value={baseRevenue}
                onChange={(e) => {
                  setBaseRevenue(e.target.value);
                  if (dcfErrors.baseRevenue) {
                    setDcfErrors((prev) => ({ ...prev, baseRevenue: false }));
                  }
                }}
                className={inputFieldClass(dcfErrors.baseRevenue)}
                placeholder="e.g. 1000"
                disabled={loading}
              />
            </label>

            <button
              type="button"
              disabled={loading}
              onClick={() => void handleCreateDcf()}
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {loading ? "Creating…" : "Create template"}
            </button>
          </div>
        )}

        {tab === "comparative" && (
          <div className="max-w-lg space-y-4">
            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-700">
                Model name <span className="font-normal text-gray-400">(optional)</span>
              </span>
              <input
                type="text"
                value={compName}
                onChange={(e) => setCompName(e.target.value)}
                className={inputFieldClass(false)}
                placeholder="Optional"
                disabled={loading}
              />
            </label>

            <label className="flex flex-col gap-1">
              <span className="text-xs font-medium text-gray-700">Target</span>
              <input
                type="text"
                value={compTarget}
                onChange={(e) => {
                  setCompTarget(e.target.value);
                  if (compErrors.target) setCompErrors((prev) => ({ ...prev, target: false }));
                }}
                className={inputFieldClass(compErrors.target)}
                placeholder="e.g. nvda"
                disabled={loading}
              />
            </label>

            <div>
              <label className="text-xs font-medium text-gray-700">Peers (up to 5)</label>
              <div className="mt-1.5">
                <ChipInput
                  values={compPeers}
                  onChange={(next) => {
                    setCompPeers(next);
                    if (compErrors.peers && next.length > 0) {
                      setCompErrors((prev) => ({ ...prev, peers: false }));
                    }
                  }}
                  maxItems={5}
                  error={compErrors.peers}
                  normalize={normalizeTicker}
                  disabled={loading}
                />
              </div>
            </div>

            <button
              type="button"
              disabled={loading}
              onClick={() => void handleCreateComparative()}
              className="rounded-lg bg-violet-600 px-4 py-2 text-sm font-medium text-white hover:bg-violet-700 disabled:opacity-50"
            >
              {loading ? "Running analysis…" : "Do comparative analysis"}
            </button>
          </div>
        )}

        {banner && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              isErrorBanner(banner)
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-violet-200 bg-violet-50 text-violet-800"
            }`}
          >
            {banner}
          </div>
        )}
      </div>
    </div>
  );
}
