import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchSessionWorkspace, API_BASE } from "../api";
import DashboardPanel from "../components/DashboardPanel";
import SessionGuideModal, { SessionGuideButton } from "../components/SessionGuideModal";
import type { DashboardSelection, FileEntry, ModelEntry } from "../types";

const POLL_MS = 3000;
const guideSeenKey = (sessionId: string) => `session-guide-seen:${sessionId}`;

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [selection, setSelection] = useState<DashboardSelection>({ kind: "none" });
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const modelCountRef = useRef(0);
  const fileCountRef = useRef(0);
  const analysisSnapshotRef = useRef<Map<string, string>>(new Map());

  const selectAndPulse = useCallback(
    (kind: "file" | "model" | "analysis", id: string) => {
      setSelection({ kind, id });
      setPulseId(id);
      window.setTimeout(() => setPulseId(null), 3200);
    },
    [],
  );

  useEffect(() => {
    if (!sessionId) return;
    if (!sessionStorage.getItem(guideSeenKey(sessionId))) {
      setGuideOpen(true);
      sessionStorage.setItem(guideSeenKey(sessionId), "1");
    }
  }, [sessionId]);

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

          let analysisToSelect: ModelEntry | undefined;
          for (const model of workspace.models) {
            if (model.type !== "detailed_analysis") continue;
            const ts =
              ("updated_at" in model && model.updated_at) ||
              model.created_at ||
              "";
            const prev = analysisSnapshotRef.current.get(model.id);
            const isNew =
              prev === undefined && workspace.models.length > prevModelCount;
            const isUpdated = prev !== undefined && prev !== ts;
            if (isNew || isUpdated) {
              analysisToSelect = model;
            }
            analysisSnapshotRef.current.set(model.id, ts);
          }

          if (analysisToSelect) {
            selectAndPulse("analysis", analysisToSelect.id);
          } else if (
            workspace.models.length > prevModelCount &&
            workspace.models.length > 0
          ) {
            const latest = workspace.models[workspace.models.length - 1];
            selectAndPulse("model", latest.id);
          } else if (
            workspace.files.length > prevFileCount &&
            workspace.files.length > 0
          ) {
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
      <SessionGuideModal open={guideOpen} onClose={() => setGuideOpen(false)} />

      <header className="shrink-0 border-b border-[var(--border-soft)] bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-base font-semibold text-gray-900">Workspace</h1>
            <p className="text-xs text-gray-500">
              Private link — files and models update as you chat with your assistant
            </p>
          </div>
          <SessionGuideButton onClick={() => setGuideOpen(true)} />
        </div>
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
          <div className="flex h-full flex-col items-center justify-center gap-3 px-6 text-center">
            <p className="text-sm text-gray-500">
              No files or models yet — use the button above for example prompts to try in chat.
            </p>
          </div>
        )}

        {!notFound && !error && hasContent && sessionId && (
          <DashboardPanel
            sessionId={sessionId}
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
