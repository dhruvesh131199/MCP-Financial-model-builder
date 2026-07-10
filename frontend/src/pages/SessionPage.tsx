import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { fetchSessionWorkspace, deleteSessionFile, deleteSessionModel, API_BASE } from "../api";
import DashboardPanel from "../components/DashboardPanel";
import { SetupMcpLink } from "../components/SessionGuideModal";
import ToolGuideModal, { ToolGuideButton } from "../components/ToolGuideModal";
import SessionIdCopy from "../components/SessionIdCopy";
import type { DashboardSelection, FileEntry, ModelEntry, FinancialsFetchLogEntry, RagDocumentEntry, SessionProcess } from "../types";
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
  const [processes, setProcesses] = useState<SessionProcess[]>([]);
  const [selection, setSelection] = useState<DashboardSelection>({ kind: "none" });
  const [pulseId, setPulseId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [toolGuideOpen, setToolGuideOpen] = useState(false);
  const modelCountRef = useRef(0);
  const fileCountRef = useRef(0);
  const analysisSnapshotRef = useRef<Map<string, string>>(new Map());
  const ragDisplayIdsRef = useRef<Set<string>>(new Set());
  const selectionRef = useRef(selection);
  const initialSyncDoneRef = useRef(false);

  useEffect(() => {
    selectionRef.current = selection;
  }, [selection]);

  const selectAndPulse = useCallback(
    (kind: "file" | "model" | "analysis" | "rag_result", id: string) => {
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
            setProcesses(workspace.processes ?? []);
            for (const model of workspace.models) {
              if (model.type === "detailed_analysis") {
                const ts =
                  ("updated_at" in model && model.updated_at) ||
                  model.created_at ||
                  "";
                analysisSnapshotRef.current.set(model.id, ts);
              }
              if (model.type === "rag_display") {
                ragDisplayIdsRef.current.add(model.id);
              }
            }
            return;
          }

          modelCountRef.current = workspace.models.length;
          fileCountRef.current = workspace.files.length;
          setModels(workspace.models);
          setFiles(workspace.files);
          setRagDocuments(workspace.rag_documents ?? []);
          setFinancialsFetchLog(workspace.financials_fetch_log ?? []);
          setProcesses(workspace.processes ?? []);

          let analysisToSelect: ModelEntry | undefined;
          let ragResultToSelect: ModelEntry | undefined;
          for (const model of workspace.models) {
            if (model.type === "detailed_analysis") {
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
            if (model.type === "rag_display" && !ragDisplayIdsRef.current.has(model.id)) {
              ragResultToSelect = model;
              ragDisplayIdsRef.current.add(model.id);
            }
          }

          if (analysisToSelect) {
            selectAndPulse("analysis", analysisToSelect.id);
          } else if (ragResultToSelect) {
            selectAndPulse("rag_result", ragResultToSelect.id);
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
        setProcesses(workspace.processes ?? []);
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
        current.kind === "model" && current.id === modelId
          ? { kind: "none" }
          : current.kind === "rag_result" && current.id === modelId
            ? { kind: "none" }
            : current,
      );
      await refreshWorkspace();
    },
    [sessionId, refreshWorkspace],
  );

  return (
    <div className="flex h-screen flex-col">
      <ToolGuideModal open={toolGuideOpen} onClose={() => setToolGuideOpen(false)} />

      <header className="shrink-0 border-b border-[var(--border-soft)] bg-white px-4 py-3">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1">
            <h1 className="text-base font-semibold text-gray-900">Workspace</h1>
            <div className="mt-0.5 flex flex-wrap items-center gap-2">
              <p className="text-xs text-gray-500">Your private workspace for 1 hour.</p>
              {sessionId && !notFound && !error && (
                <SessionIdCopy sessionId={sessionId} />
              )}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <SetupMcpLink />
            <ToolGuideButton onClick={() => setToolGuideOpen(true)} />
          </div>
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
            processes={processes}
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
