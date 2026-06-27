import type {
  DashboardSelection,
  DetailedAnalysisModelEntry,
  DcfModelEntry,
  DcfResult,
  FileEntry,
  ModelEntry,
} from "../types";
import { exportComparativeToExcel } from "../utils/exportComparativeExcel";
import { exportDcfTemplateExcel, exportDcfToExcel } from "../utils/exportDcfExcel";
import { exportFinancialsToExcel } from "../utils/exportFinancialsExcel";
import ComparativeTable from "./ComparativeTable";
import DcfEditor from "./DcfEditor";
import DcfTable from "./DcfTable";
import DetailedAnalysisViewer from "./DetailedAnalysisViewer";
import FileViewer from "./FileViewer";
import { useMemo, useState, type ReactNode } from "react";

interface DashboardPanelProps {
  sessionId: string;
  files: FileEntry[];
  models: ModelEntry[];
  selection: DashboardSelection;
  pulseId: string | null;
  onSelect: (selection: DashboardSelection) => void;
}

export default function DashboardPanel({
  sessionId,
  files,
  models,
  selection,
  pulseId,
  onSelect,
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

  const detailedAnalyses = useMemo(
    () =>
      models.filter(
        (m): m is DetailedAnalysisModelEntry => m.type === "detailed_analysis",
      ),
    [models],
  );

  const displayFiles = useMemo(() => dedupeByTicker(files), [files]);
  const displayAnalyses = useMemo(
    () => dedupeAnalysesByTicker(detailedAnalyses),
    [detailedAnalyses],
  );

  const activeFile =
    selection.kind === "file"
      ? displayFiles.find((f) => f.id === selection.id)
      : undefined;
  const activeModel =
    selection.kind === "model"
      ? sidebarModels.find((m) => m.id === selection.id)
      : undefined;
  const activeAnalysis =
    selection.kind === "analysis"
      ? displayAnalyses.find((m) => m.id === selection.id)
      : undefined;

  const activeDraft =
    selection.kind === "model" && activeModel?.type === "dcf_draft"
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
        <SidebarSection title="Files">
          {displayFiles.length === 0 ? (
            <EmptyHint text="Fetched files will appear here" />
          ) : (
            displayFiles.map((file) => (
              <SidebarItem
                key={file.id}
                label={file.data.ticker || file.name}
                active={selection.kind === "file" && selection.id === file.id}
                pulse={pulseId === file.id}
                onClick={() => onSelect({ kind: "file", id: file.id })}
              />
            ))
          )}
        </SidebarSection>

        <SidebarSection title="Models">
          {sidebarModels.length === 0 ? (
            <EmptyHint text="Built models will appear here" />
          ) : (
            sidebarModels.map((model) => (
              <SidebarItem
                key={model.id}
                label={model.name}
                active={selection.kind === "model" && selection.id === model.id}
                pulse={pulseId === model.id}
                onClick={() => onSelect({ kind: "model", id: model.id })}
              />
            ))
          )}
        </SidebarSection>

        <SidebarSection title="Detailed Analysis">
          {displayAnalyses.length === 0 ? (
            <EmptyHint text="Run detailed analysis from chat" />
          ) : (
            displayAnalyses.map((entry) => (
              <SidebarItem
                key={entry.id}
                label={entry.data.ticker}
                active={
                  selection.kind === "analysis" && selection.id === entry.id
                }
                pulse={pulseId === entry.id}
                onClick={() => onSelect({ kind: "analysis", id: entry.id })}
              />
            ))
          )}
        </SidebarSection>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col bg-white">
        {activeDraft?.type === "dcf_draft" ? (
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
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            Select a file, model, or detailed analysis from the sidebar
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
          className="rounded-lg border border-indigo-200/80 bg-white px-3 py-1.5 text-xs font-medium text-indigo-600 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 disabled:opacity-50"
        >
          {downloading ? "Exporting…" : "Download .xlsx"}
        </button>
      )}
    </div>
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
  active,
  pulse,
  onClick,
}: {
  label: string;
  active: boolean;
  pulse: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`truncate rounded-lg px-2 py-1.5 text-left text-xs transition ${
        active
          ? "bg-indigo-100 font-medium text-indigo-900"
          : "text-gray-700 hover:bg-white/80"
      } ${pulse ? "ring-2 ring-indigo-300" : ""}`}
    >
      {label}
    </button>
  );
}

function EmptyHint({ text }: { text: string }) {
  return <p className="px-2 py-1 text-[11px] text-gray-400">{text}</p>;
}
