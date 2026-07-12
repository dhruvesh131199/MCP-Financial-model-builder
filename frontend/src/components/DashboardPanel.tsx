import type {
  DashboardSelection,
  DetailedAnalysisModelEntry,
  DcfModelEntry,
  DcfResult,
  FileEntry,
  FinancialsFetchLogEntry,
  ModelEntry,
  RagDisplayModelEntry,
  RagDocumentEntry,
  SessionProcess,
} from "../types";
import { exportComparativeToExcel } from "../utils/exportComparativeExcel";
import { exportDcfTemplateExcel, exportDcfToExcel } from "../utils/exportDcfExcel";
import { exportFinancialsToExcel } from "../utils/exportFinancialsExcel";
import ComparativeTable from "./ComparativeTable";
import DcfEditor from "./DcfEditor";
import DcfTable from "./DcfTable";
import DetailedAnalysisViewer from "./DetailedAnalysisViewer";
import FileViewer from "./FileViewer";
import FetchFinancialsHubPanel from "./FetchFinancialsHubPanel";
import ModelsHubPanel from "./ModelsHubPanel";
import RagDisplayViewer from "./RagDisplayViewer";
import RagHubPanel from "./RagHubPanel";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { resolveOrphanModelSelection } from "../lib/sessionAutoSelect";
import { ragDocumentDisplayLabel } from "../lib/ragDocumentLabel";

interface DashboardPanelProps {
  sessionId: string;
  files: FileEntry[];
  models: ModelEntry[];
  ragDocuments: RagDocumentEntry[];
  financialsFetchLog: FinancialsFetchLogEntry[];
  processes: SessionProcess[];
  selection: DashboardSelection;
  pulseId: string | null;
  onSelect: (selection: DashboardSelection) => void;
  onRagRefresh: () => void;
  onFinancialsRefresh: () => void;
  onModelsRefresh: () => void;
  onDeleteFile: (fileId: string) => void | Promise<void>;
  onDeleteModel: (modelId: string) => void | Promise<void>;
}

export default function DashboardPanel({
  sessionId,
  files,
  models,
  ragDocuments,
  financialsFetchLog,
  processes,
  selection,
  pulseId,
  onSelect,
  onRagRefresh,
  onFinancialsRefresh,
  onModelsRefresh,
  onDeleteFile,
  onDeleteModel,
}: DashboardPanelProps) {
  const [downloading, setDownloading] = useState(false);

  const sidebarModels = useMemo(
    () =>
      models.filter((m) => {
        if (m.type === "dcf_draft" || m.type === "comparative") return true;
        if (m.type === "dcf") {
          const twin =
            (m as DcfModelEntry).draft_id ?? (m as DcfModelEntry).data?.draft_id;
          return !twin;
        }
        return false;
      }),
    [models],
  );

  const sidebarModelIds = useMemo(
    () => sidebarModels.map((m) => m.id),
    [sidebarModels],
  );

  const effectiveSelection = useMemo(
    () => resolveOrphanModelSelection(selection, sidebarModelIds, models),
    [selection, sidebarModelIds, models],
  );

  useEffect(() => {
    const unchanged =
      effectiveSelection.kind === selection.kind &&
      (effectiveSelection.kind === "none" ||
        effectiveSelection.kind === "rag_hub" ||
        effectiveSelection.kind === "financials_hub" ||
        effectiveSelection.kind === "models_hub" ||
        ((effectiveSelection.kind === "file" ||
          effectiveSelection.kind === "model" ||
          effectiveSelection.kind === "analysis" ||
          effectiveSelection.kind === "rag_result") &&
          selection.kind === effectiveSelection.kind &&
          effectiveSelection.id === selection.id));
    if (unchanged) return;
    onSelect(effectiveSelection);
  }, [effectiveSelection, selection, onSelect]);

  const detailedAnalyses = useMemo(
    () =>
      models.filter(
        (m): m is DetailedAnalysisModelEntry => m.type === "detailed_analysis",
      ),
    [models],
  );

  const ragResults = useMemo(
    () => models.filter((m): m is RagDisplayModelEntry => m.type === "rag_display"),
    [models],
  );

  const displayFiles = useMemo(() => dedupeByTicker(files), [files]);
  const displayAnalyses = useMemo(
    () => dedupeAnalysesByTicker(detailedAnalyses),
    [detailedAnalyses],
  );

  const activeFile =
    effectiveSelection.kind === "file"
      ? displayFiles.find((f) => f.id === effectiveSelection.id)
      : undefined;
  const activeModel =
    effectiveSelection.kind === "model"
      ? sidebarModels.find((m) => m.id === effectiveSelection.id)
      : undefined;

  const activeAnalysis =
    effectiveSelection.kind === "analysis"
      ? displayAnalyses.find((m) => m.id === effectiveSelection.id)
      : undefined;

  const activeRagResult =
    effectiveSelection.kind === "rag_result"
      ? ragResults.find((m) => m.id === effectiveSelection.id)
      : undefined;

  const showRagHub = effectiveSelection.kind === "rag_hub";
  const showFinancialsHub = effectiveSelection.kind === "financials_hub";
  const showModelsHub = effectiveSelection.kind === "models_hub";

  const activeDraft =
    effectiveSelection.kind === "model" && activeModel?.type === "dcf_draft"
      ? activeModel
      : undefined;

  const computedForDraft: DcfResult | null = useMemo(() => {
    if (!activeDraft) return null;
    const cid = activeDraft.data.computed_model_id;
    if (!cid) return null;
    const entry = models.find((m) => m.id === cid && m.type === "dcf");
    return entry?.type === "dcf" ? entry.data : null;
  }, [activeDraft, models]);

  async function handleDownload() {
    if (activeDraft?.type === "dcf_draft") {
      setDownloading(true);
      try {
        await exportDcfTemplateExcel(activeDraft.data, activeDraft.name);
      } finally {
        setDownloading(false);
      }
      return;
    }
    if (activeModel?.type === "dcf") {
      setDownloading(true);
      try {
        await exportDcfToExcel(activeModel.data, activeModel.name);
      } finally {
        setDownloading(false);
      }
      return;
    }
    if (activeModel?.type === "comparative") {
      setDownloading(true);
      try {
        await exportComparativeToExcel(activeModel.data, activeModel.name);
      } finally {
        setDownloading(false);
      }
      return;
    }
    if (activeFile?.type === "financials") {
      setDownloading(true);
      try {
        await exportFinancialsToExcel(activeFile.data, activeFile.name);
      } finally {
        setDownloading(false);
      }
    }
  }

  const showDownload = Boolean(
    (activeModel && activeModel.type !== "dcf_draft") || activeFile,
  );

  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-[20%] min-w-[180px] flex-col overflow-y-auto border-r border-[var(--border-soft)] bg-[var(--bg-sidebar)]">
        <ProcessingSidebarSection processes={processes} />

        <FetchFinancialsSidebarSection
          hubActive={effectiveSelection.kind === "financials_hub"}
          onSelectHub={() => onSelect({ kind: "financials_hub" })}
          files={displayFiles}
          activeFileId={effectiveSelection.kind === "file" ? effectiveSelection.id : null}
          pulseId={pulseId}
          onSelectFile={(id) => onSelect({ kind: "file", id })}
          onDeleteFile={onDeleteFile}
        />

        <ModelsSidebarSection
          hubActive={effectiveSelection.kind === "models_hub"}
          onSelectHub={() => onSelect({ kind: "models_hub" })}
          models={sidebarModels}
          activeModelId={effectiveSelection.kind === "model" ? effectiveSelection.id : null}
          pulseId={pulseId}
          onSelectModel={(id) => onSelect({ kind: "model", id })}
          onDeleteModel={onDeleteModel}
        />

        <SidebarSection title="Detailed Analysis">
          {displayAnalyses.length === 0 ? (
            <EmptyHint text='Ask your LLM: “Do detailed analysis of Microsoft”' />
          ) : (
            displayAnalyses.map((entry) => (
              <SidebarItem
                key={entry.id}
                label={entry.data.ticker}
                title={entry.data.ticker}
                active={
                  effectiveSelection.kind === "analysis" && effectiveSelection.id === entry.id
                }
                pulse={pulseId === entry.id}
                onClick={() => onSelect({ kind: "analysis", id: entry.id })}
              />
            ))
          )}
        </SidebarSection>

        <RagResultsSidebarSection
          results={ragResults}
          activeId={effectiveSelection.kind === "rag_result" ? effectiveSelection.id : null}
          pulseId={pulseId}
          onSelect={(id) => onSelect({ kind: "rag_result", id })}
          onDelete={onDeleteModel}
        />

        <RagSidebarSection
          hubActive={effectiveSelection.kind === "rag_hub"}
          onSelectHub={() => onSelect({ kind: "rag_hub" })}
          documents={ragDocuments}
        />
      </aside>

      <main className="flex min-w-0 flex-1 flex-col bg-white">
        {showModelsHub ? (
          <ModelsHubPanel
            sessionId={sessionId}
            onRefresh={onModelsRefresh}
            onCreated={(modelId) => onSelect({ kind: "model", id: modelId })}
          />
        ) : showFinancialsHub ? (
          <FetchFinancialsHubPanel
            sessionId={sessionId}
            fetchLog={financialsFetchLog}
            onRefresh={onFinancialsRefresh}
          />
        ) : showRagHub ? (
          <RagHubPanel
            sessionId={sessionId}
            documents={ragDocuments}
            onRefresh={onRagRefresh}
          />
        ) : activeDraft?.type === "dcf_draft" ? (
          <DcfEditor
            sessionId={sessionId}
            modelId={activeDraft.id}
            draft={activeDraft.data}
            modelName={activeDraft.name}
            computedResult={computedForDraft}
          />
        ) : activeModel?.type === "dcf" ? (
          <>
            <ModelHeader
              name={activeModel.name}
              showDownload={showDownload}
              downloading={downloading}
              onDownload={handleDownload}
            />
            <div className="min-h-0 flex-1 overflow-hidden">
              <DcfTable model={activeModel.data} />
            </div>
          </>
        ) : activeModel?.type === "comparative" ? (
          <>
            <ModelHeader
              name={activeModel.name}
              showDownload={showDownload}
              downloading={downloading}
              onDownload={handleDownload}
            />
            <div className="min-h-0 flex-1 overflow-hidden">
              <ComparativeTable report={activeModel.data} />
            </div>
          </>
        ) : activeRagResult ? (
          <div className="min-h-0 flex-1 overflow-hidden">
            <RagDisplayViewer entry={activeRagResult} />
          </div>
        ) : activeAnalysis ? (
          <div className="min-h-0 flex-1 overflow-hidden">
            <DetailedAnalysisViewer analysis={activeAnalysis.data} />
          </div>
        ) : activeFile ? (
          <>
            <ModelHeader
              name={activeFile.data.ticker || activeFile.name}
              showDownload={showDownload}
              downloading={downloading}
              onDownload={handleDownload}
            />
            <div className="min-h-0 flex-1 overflow-hidden">
              <FileViewer
                file={activeFile}
                hasDetailedAnalysis={displayAnalyses.some(
                  (a) =>
                    a.data.ticker.toUpperCase() ===
                    activeFile.data.ticker.toUpperCase(),
                )}
              />
            </div>
          </>
        ) : (
          <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-sm text-gray-500">
            <p>Select a file, model, analysis, or RAG result from the sidebar.</p>
            <p className="text-xs text-gray-400">
              Use <span className="font-medium">Fetch Financials</span> for structured SEC tables,
              RAG Results for pinned chat answers, or the RAG section for full 10-K documents.
            </p>
          </div>
        )}
      </main>
    </div>
  );
}

function dedupeByTicker(files: FileEntry[]): FileEntry[] {
  const byTicker = new Map<string, FileEntry>();
  for (const file of files) {
    const ticker = (file.data?.ticker ?? file.name).toUpperCase();
    const existing = byTicker.get(ticker);
    if (!existing) {
      byTicker.set(ticker, file);
      continue;
    }
    const existingTs = existing.updated_at ?? existing.created_at ?? "";
    const fileTs = file.updated_at ?? file.created_at ?? "";
    if (fileTs >= existingTs) {
      byTicker.set(ticker, file);
    }
  }
  return [...byTicker.values()].sort((a, b) =>
    (a.created_at ?? "").localeCompare(b.created_at ?? ""),
  );
}

function dedupeAnalysesByTicker(
  entries: DetailedAnalysisModelEntry[],
): DetailedAnalysisModelEntry[] {
  const byTicker = new Map<string, DetailedAnalysisModelEntry>();
  for (const entry of entries) {
    const ticker = entry.data.ticker.toUpperCase();
    const existing = byTicker.get(ticker);
    if (!existing) {
      byTicker.set(ticker, entry);
      continue;
    }
    const existingTs = existing.updated_at ?? existing.created_at ?? "";
    const entryTs = entry.updated_at ?? entry.created_at ?? "";
    if (entryTs >= existingTs) {
      byTicker.set(ticker, entry);
    }
  }
  return [...byTicker.values()].sort((a, b) =>
    (a.created_at ?? "").localeCompare(b.created_at ?? ""),
  );
}

function ModelHeader({
  name,
  showDownload,
  downloading,
  onDownload,
}: {
  name: string;
  showDownload: boolean;
  downloading: boolean;
  onDownload: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between border-b border-[var(--border-soft)] bg-gradient-to-r from-white to-indigo-50/30 px-4 py-2.5">
      <span className="text-sm font-medium text-indigo-900/80">{name}</span>
      {showDownload && (
        <button
          type="button"
          onClick={onDownload}
          disabled={downloading}
          className="rounded-lg border border-indigo-200/80 bg-white px-3 py-1.5 text-xs font-medium text-indigo-600 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {downloading ? "Exporting…" : "Download .xlsx"}
        </button>
      )}
    </div>
  );
}

const sidebarActiveClass =
  "border-indigo-400/70 bg-white shadow-[0_4px_16px_rgba(99,102,241,0.45)] ring-1 ring-indigo-300/50";

const sidebarHubButtonClass = (active: boolean) =>
  [
    "flex w-full cursor-pointer items-center gap-1.5 rounded-lg border border-gray-200/80 bg-gray-50/90 px-2.5 py-2 text-left shadow-sm transition-shadow duration-150",
    active ? sidebarActiveClass : "hover:shadow-md hover:shadow-indigo-300/30",
  ].join(" ");

function ModelsSidebarSection({
  hubActive,
  onSelectHub,
  models,
  activeModelId,
  pulseId,
  onSelectModel,
  onDeleteModel,
}: {
  hubActive: boolean;
  onSelectHub: () => void;
  models: ModelEntry[];
  activeModelId: string | null;
  pulseId: string | null;
  onSelectModel: (id: string) => void;
  onDeleteModel: (id: string) => void | Promise<void>;
}) {
  return (
    <div className="flex flex-col border-b border-[var(--border-soft)] p-2">
      <button
        type="button"
        onClick={onSelectHub}
        className={sidebarHubButtonClass(hubActive)}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-600">
          Models
        </span>
      </button>
      <div className="mt-1 flex flex-col gap-0.5">
        {models.length === 0 ? (
          <EmptyHint text="Built models appear here" />
        ) : (
          models.map((model) => (
            <SidebarItem
              key={model.id}
              label={model.name}
              active={activeModelId === model.id}
              pulse={pulseId === model.id}
              onClick={() => onSelectModel(model.id)}
              onDelete={() => void onDeleteModel(model.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function ProcessingSidebarSection({ processes }: { processes: SessionProcess[] }) {
  type ChipRow = SessionProcess & { leaving?: boolean };
  const [chips, setChips] = useState<ChipRow[]>(() =>
    processes.map((p) => ({ ...p, leaving: false })),
  );
  const [sectionLeaving, setSectionLeaving] = useState(false);
  const [sectionVisible, setSectionVisible] = useState(processes.length > 0);

  useEffect(() => {
    setChips((prev) => {
      const nextIds = new Set(processes.map((p) => p.id));
      const live = processes.map((p) => ({ ...p, leaving: false }));
      const stillLeaving = prev.filter((p) => p.leaving && !nextIds.has(p.id));
      const newlyGone = prev
        .filter((p) => !p.leaving && !nextIds.has(p.id))
        .map((p) => ({ ...p, leaving: true }));
      return [...live, ...stillLeaving, ...newlyGone];
    });
  }, [processes]);

  useEffect(() => {
    const leavingIds = chips.filter((c) => c.leaving).map((c) => c.id);
    if (leavingIds.length === 0) return;
    const t = window.setTimeout(() => {
      setChips((prev) => prev.filter((c) => !leavingIds.includes(c.id)));
    }, 220);
    return () => window.clearTimeout(t);
  }, [chips]);

  const hasChips = chips.length > 0;

  useEffect(() => {
    if (hasChips) {
      setSectionLeaving(false);
      setSectionVisible(true);
      return;
    }
    if (!sectionVisible) return;
    setSectionLeaving(true);
    const t = window.setTimeout(() => {
      setSectionVisible(false);
      setSectionLeaving(false);
    }, 240);
    return () => window.clearTimeout(t);
  }, [hasChips, sectionVisible]);

  if (!sectionVisible) return null;

  return (
    <div
      className={`flex flex-col border-b border-[var(--border-soft)] p-2 process-section ${
        sectionLeaving ? "process-section-out" : "process-section-in"
      }`}
    >
      <div className="px-2 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-violet-700">
        Processing
      </div>
      <div className="mt-0.5 flex flex-col gap-1.5">
        {chips.map((proc) => {
          const pct = Math.max(0, Math.min(100, Number(proc.progress) || 0));
          return (
            <div
              key={proc.id}
              title={proc.process_name}
              className={`process-chip-shimmer overflow-hidden rounded-md border border-violet-200/80 px-2 py-1.5 ${
                proc.leaving ? "process-chip-out" : "process-chip-in"
              }`}
            >
              <p
                className="truncate text-xs font-medium text-gray-800"
                title={proc.process_name}
              >
                {proc.process_name}
              </p>
              <p
                className="mt-0.5 truncate text-[10px] leading-snug text-gray-500"
                title={proc.message}
              >
                {proc.message}
              </p>
              <div className="mt-1.5 h-0.5 w-full overflow-hidden rounded-full bg-violet-100">
                <div
                  className="h-full rounded-full bg-sky-400 transition-[width] duration-500 ease-out"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function FetchFinancialsSidebarSection({
  hubActive,
  onSelectHub,
  files,
  activeFileId,
  pulseId,
  onSelectFile,
  onDeleteFile,
}: {
  hubActive: boolean;
  onSelectHub: () => void;
  files: FileEntry[];
  activeFileId: string | null;
  pulseId: string | null;
  onSelectFile: (id: string) => void;
  onDeleteFile: (id: string) => void | Promise<void>;
}) {
  return (
    <div className="flex flex-col border-b border-[var(--border-soft)] p-2">
      <button
        type="button"
        onClick={onSelectHub}
        className={sidebarHubButtonClass(hubActive)}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-600">
          Fetch Financials
        </span>
      </button>
      <div className="mt-1 flex flex-col gap-0.5">
        {files.length === 0 ? (
          <EmptyHint text="Fetched tickers appear here" />
        ) : (
          files.map((file) => (
            <SidebarItem
              key={file.id}
              label={file.data.ticker || file.name}
              active={activeFileId === file.id}
              pulse={pulseId === file.id}
              onClick={() => onSelectFile(file.id)}
              onDelete={() => void onDeleteFile(file.id)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function RagSidebarSection({
  hubActive,
  onSelectHub,
  documents,
}: {
  hubActive: boolean;
  onSelectHub: () => void;
  documents: RagDocumentEntry[];
}) {
  const readyDocs = documents.filter((doc) => doc.status === "ready");
  return (
    <div className="flex flex-col border-b border-[var(--border-soft)] p-2">
      <button
        type="button"
        onClick={onSelectHub}
        className={sidebarHubButtonClass(hubActive)}
      >
        <span className="text-[10px] font-semibold uppercase tracking-wide text-gray-600">
          Upload financial document for your questions!
        </span>
        <span className="shrink-0 rounded bg-indigo-600 px-1 py-0.5 text-[8px] font-bold uppercase text-white">
          RAG
        </span>
      </button>
      {readyDocs.length > 0 && (
        <ul className="mt-1.5 space-y-0.5 px-2">
          {readyDocs.map((doc) => (
            <li
              key={doc.id}
              className="truncate py-0.5 text-xs text-gray-600"
              title={ragDocumentDisplayLabel(doc)}
            >
              {ragDocumentDisplayLabel(doc)}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function RagResultsSidebarSection({
  results,
  activeId,
  pulseId,
  onSelect,
  onDelete,
}: {
  results: RagDisplayModelEntry[];
  activeId: string | null;
  pulseId: string | null;
  onSelect: (id: string) => void;
  onDelete: (id: string) => void | Promise<void>;
}) {
  return (
    <SidebarSection title="RAG Results">
      {results.length === 0 ? (
        <EmptyHint text="Pinned chat answers appear here" />
      ) : (
        results.map((entry) => (
          <SidebarItem
            key={entry.id}
            label={entry.name}
            title={entry.name}
            active={activeId === entry.id}
            pulse={pulseId === entry.id}
            onClick={() => onSelect(entry.id)}
            onDelete={() => void onDelete(entry.id)}
          />
        ))
      )}
    </SidebarSection>
  );
}

function SidebarSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col border-b border-[var(--border-soft)] p-2">
      <h3 className="mb-1.5 px-2 text-[10px] font-semibold uppercase tracking-wide text-gray-500">
        {title}
      </h3>
      <div className="flex flex-col gap-0.5">{children}</div>
    </div>
  );
}

function SidebarItem({
  label,
  title,
  active,
  pulse,
  onClick,
  onDelete,
}: {
  label: string;
  title?: string;
  active: boolean;
  pulse: boolean;
  onClick: () => void;
  onDelete?: () => void;
}) {
  return (
    <div
      className={`group flex items-center gap-0.5 rounded-lg transition ${
        active ? "bg-indigo-100" : "hover:bg-white/80"
      } ${pulse ? "ring-2 ring-indigo-300" : ""}`}
    >
      <button
        type="button"
        onClick={onClick}
        title={title ?? label}
        className={`min-w-0 flex-1 truncate px-2 py-1.5 text-left text-xs ${
          active ? "font-medium text-indigo-900" : "text-gray-700"
        }`}
      >
        {label}
      </button>
      {onDelete && (
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onDelete();
          }}
          aria-label={`Delete ${label}`}
          className="mr-1 shrink-0 rounded p-1 text-gray-400 opacity-0 transition hover:text-red-600 group-hover:opacity-100"
        >
          <TrashIcon />
        </button>
      )}
    </div>
  );
}

function TrashIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox="0 0 16 16"
      fill="currentColor"
      className="h-3.5 w-3.5"
      aria-hidden
    >
      <path
        fillRule="evenodd"
        d="M5 3.25V4H2.75a.75.75 0 0 0 0 1.5h.317l.856 8.384A1.75 1.75 0 0 0 5.676 15h4.648a1.75 1.75 0 0 0 1.742-1.616l.856-8.384h.317a.75.75 0 0 0 0-1.5H11v-.75A1.75 1.75 0 0 0 9.25 2h-2.5A1.75 1.75 0 0 0 5 3.25Zm2.25-.75a.25.25 0 0 1 .25-.25h2.5a.25.25 0 0 1 .25.25V4H7.25ZM4.14 6.002l.807 7.884a.25.25 0 0 0 .249.228h4.648a.25.25 0 0 0 .249-.228l.807-7.884H4.14Z"
        clipRule="evenodd"
      />
    </svg>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <p className="px-2 py-1 text-[11px] text-gray-400">{text}</p>;
}
