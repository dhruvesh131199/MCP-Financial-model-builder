import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchSessionWorkspace, API_BASE } from "../api";
import DashboardPanel from "../components/DashboardPanel";
import type { DashboardSelection, DcfModelEntry } from "../types";

const POLL_MS = 3000;

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [models, setModels] = useState<DcfModelEntry[]>([]);
  const [selection, setSelection] = useState<DashboardSelection>({ kind: "none" });
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const modelCountRef = useRef(0);

  const selectAndPulse = useCallback((id: string) => {
    setSelection({ kind: "model", id });
    setPulseId(id);
    window.setTimeout(() => setPulseId(null), 3200);
  }, []);

  useEffect(() => {
    if (!sessionId) return;
    const sid = sessionId;

    let cancelled = false;
    let lastUpdated: string | null = null;

    async function poll() {
      try {
        const workspace = await fetchSessionWorkspace(sid);
        if (cancelled) return;
        setError(null);
        setNotFound(!workspace.exists);

        if (workspace.updated_at !== lastUpdated) {
          lastUpdated = workspace.updated_at;
          const prevCount = modelCountRef.current;
          modelCountRef.current = workspace.models.length;
          setModels(workspace.models);

          if (workspace.models.length > prevCount && workspace.models.length > 0) {
            const latest = workspace.models[workspace.models.length - 1];
            selectAndPulse(latest.id);
          }
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to fetch workspace");
        }
      }
    }

    poll();
    const id = window.setInterval(poll, POLL_MS);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [sessionId, selectAndPulse]);

  return (
    <div className="flex h-screen flex-col">
      <header className="shrink-0 border-b border-[var(--border-soft)] bg-white px-4 py-3">
        <h1 className="text-base font-semibold text-gray-900">Workspace</h1>
        <p className="text-xs text-gray-500">
          Private link — models update as you chat in Cursor
        </p>
      </header>

      <div className="min-h-0 flex-1">
        {error && (
          <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            Cannot reach API at {API_BASE} — is the backend running?
          </div>
        )}

        {notFound && !error && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-gray-500">Session not found</p>
          </div>
        )}

        {!notFound && !error && models.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-gray-500">
              No models yet — ask Cursor to build a DCF
            </p>
          </div>
        )}

        {!notFound && !error && models.length > 0 && (
          <DashboardPanel
            models={models}
            selection={selection}
            pulseId={pulseId}
            onSelect={setSelection}
          />
        )}
      </div>
    </div>
  );
}
