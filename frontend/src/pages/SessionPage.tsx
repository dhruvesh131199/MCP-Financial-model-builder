import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchSessionWorkspace, API_BASE } from "../api";
import DashboardPanel from "../components/DashboardPanel";
import type { DashboardSelection, DcfModelEntry, FileEntry } from "../types";

const POLL_MS = 3000;

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [models, setModels] = useState<DcfModelEntry[]>([]);
  const [selection, setSelection] = useState<DashboardSelection>({ kind: "none" });
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const modelCountRef = useRef(0);
  const fileCountRef = useRef(0);

  const selectAndPulse = useCallback((kind: "file" | "model", id: string) => {
    setSelection({ kind, id });
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
          const prevModelCount = modelCountRef.current;
          const prevFileCount = fileCountRef.current;
          modelCountRef.current = workspace.models.length;
          fileCountRef.current = workspace.files.length;
          setModels(workspace.models);
          setFiles(workspace.files);

          if (workspace.models.length > prevModelCount && workspace.models.length > 0) {
            const latest = workspace.models[workspace.models.length - 1];
            selectAndPulse("model", latest.id);
          } else if (workspace.files.length > prevFileCount && workspace.files.length > 0) {
            const latest = workspace.files[workspace.files.length - 1];
            selectAndPulse("file", latest.id);
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

  const hasContent = models.length > 0 || files.length > 0;

  return (
    <div className="flex h-screen flex-col">
      <header className="shrink-0 border-b border-[var(--border-soft)] bg-white px-4 py-3">
        <h1 className="text-base font-semibold text-gray-900">Workspace</h1>
        <p className="text-xs text-gray-500">
          Private link — files and models update as you chat in Cursor
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

        {!notFound && !error && !hasContent && (
          <div className="flex h-full items-center justify-center">
            <p className="text-sm text-gray-500">
              No files or models yet — ask Cursor to fetch SEC financials or build a DCF
            </p>
          </div>
        )}

        {!notFound && !error && hasContent && (
          <DashboardPanel
            files={files}
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
