import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchSessionWorkspace, markSessionGuideSeen, deleteSessionFile, deleteSessionModel, API_BASE } from "../api";
import DashboardPanel from "../components/DashboardPanel";
import SessionGuideModal, { SessionGuideButton } from "../components/SessionGuideModal";
import type { DashboardSelection, FileEntry, ModelEntry, FinancialsFetchLogEntry, RagDocumentEntry } from "../types";
import {
  resolveNewModelAutoSelect,
} from "../lib/sessionAutoSelect";

const POLL_MS = 3000;

export default function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const [files, setFiles] = useState<FileEntry[]>([]);
  const [models, setModels] = useState<ModelEntry[]>([]);
  const [ragDocuments, setRagDocuments] = useState<RagDocumentEntry[]>([]);
  const [financialsFetchLog, setFinancialsFetchLog] = useState<FinancialsFetchLogEntry[]>([]);
  const [selection, setSelection] = useState<DashboardSelection>({ kind: "none" });
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [guideOpen, setGuideOpen] = useState(false);
  const modelCountRef = useRef(0);
  const fileCountRef = useRef(0);
  const analysisSnapshotRef = useRef<Map<string, string>>(new Map());
  const selectionRef = useRef(selection);
  const initialSyncDoneRef = useRef(false);
  const guideCheckedRef = useRef(false);

  useEffect(() => {
    selectionRef.current = selection;
  }, [selection]);

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
    const sid = sessionId;

    let cancelled = false;
    let lastUpdated: string | null = null;

    async function poll() {
      try {
        const workspace = await fetchSessionWorkspace(sid);
        if (cancelled) return;
        setError(null);
        setNotFound(!workspace.exists);

        if (workspace.exists && !guideCheckedRef.current) {
          guideCheckedRef.current = true;
          if (workspace.guide_seen === false) {
            setGuideOpen(true);
          }
        }

        if (workspace.updated_at !== lastUpdated) {
          lastUpdated = workspace.updated_at;
          const prevModelCount = modelCountRef.current;
          const prevFileCount = fileCountRef.current;

          if (!initialSyncDoneRef.current) {
            initialSyncDoneRef.current = true;
            modelCountRef.current = workspace.models.length;
            fileCountRef.current = workspace.files.length;
            setModels(workspace.models);
            setFiles(workspace.files);
            setRagDocuments(workspace.rag_documents ?? []);
            setFinancialsFetchLog(workspace.financials_fetch_log ?? []);
            for (const model of workspace.models) {
              if (model.type !== "detailed_analysis") continue;
              const ts =
                ("updated_at" in model && model.updated_at) ||
                model.created_at ||
                "";
              analysisSnapshotRef.current.set(model.id, ts);
            }
            return;
          }

          modelCountRef.current = workspace.models.length;
          fileCountRef.current = workspace.files.length;
          setModels(workspace.models);
          setFiles(workspace.files);
          setRagDocuments(workspace.rag_documents ?? []);
          setFinancialsFetchLog(workspace.financials_fetch_log ?? []);

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
            const next = resolveNewModelAutoSelect(latest, selectionRef.current);
            if (next) {
              selectAndPulse(next.kind, next.id);
            }
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

  const refreshWorkspace = useCallback(async () => {
    if (!sessionId) return;
    try {
      const workspace = await fetchSessionWorkspace(sessionId);
      if (workspace.exists) {
        setRagDocuments(workspace.rag_documents ?? []);
        setFinancialsFetchLog(workspace.financials_fetch_log ?? []);
        setModels(workspace.models);
        setFiles(workspace.files);
      }
    } catch {
      /* poll will retry */
    }
  }, [sessionId]);

  const handleDeleteFile = useCallback(
    async (fileId: string) => {
      if (!sessionId) return;
      await deleteSessionFile(sessionId, fileId);
      setSelection((current) =>
        current.kind === "file" && current.id === fileId ? { kind: "none" } : current,
      );
      await refreshWorkspace();
    },
    [sessionId, refreshWorkspace],
  );

  const handleDeleteModel = useCallback(
    async (modelId: string) => {
      if (!sessionId) return;
      await deleteSessionModel(sessionId, modelId);
      setSelection((current) =>
        current.kind === "model" && current.id === modelId ? { kind: "none" } : current,
      );
      await refreshWorkspace();
    },
    [sessionId, refreshWorkspace],
  );

  const dismissGuide = useCallback(() => {
    setGuideOpen(false);
    if (sessionId) {
      void markSessionGuideSeen(sessionId).catch(() => {
        /* best-effort; user can reopen via button */
      });
    }
  }, [sessionId]);

  return (
    <div className="flex h-screen flex-col">
      <SessionGuideModal open={guideOpen} onClose={dismissGuide} />

      <header className="shrink-0 border-b border-[var(--border-soft)] bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0">
            <h1 className="text-base font-semibold text-gray-900">Workspace</h1>
            <p className="text-xs text-gray-500">
              Private analyzer workspace — updates as you chat with your assistant
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

        {!notFound && !error && sessionId && (
          <DashboardPanel
            sessionId={sessionId}
            files={files}
            models={models}
            ragDocuments={ragDocuments}
            financialsFetchLog={financialsFetchLog}
            selection={selection}
            pulseId={pulseId}
            onSelect={setSelection}
            onRagRefresh={() => void refreshWorkspace()}
            onFinancialsRefresh={() => void refreshWorkspace()}
            onModelsRefresh={() => void refreshWorkspace()}
            onDeleteFile={handleDeleteFile}
            onDeleteModel={handleDeleteModel}
          />
        )}
      </div>
    </div>
  );
}
