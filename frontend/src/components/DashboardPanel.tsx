import type { DashboardSelection, FileEntry, ModelEntry } from "../types";
import { exportComparativeToExcel } from "../utils/exportComparativeExcel";
import { exportDcfToExcel } from "../utils/exportDcfExcel";
import { exportFinancialsToExcel } from "../utils/exportFinancialsExcel";
import ComparativeTable from "./ComparativeTable";
import DcfTable from "./DcfTable";
import FileViewer from "./FileViewer";
import { useState, type ReactNode } from "react";

interface DashboardPanelProps {
  files: FileEntry[];
  models: ModelEntry[];
  selection: DashboardSelection;
  pulseId: string | null;
  onSelect: (selection: DashboardSelection) => void;
}

export default function DashboardPanel({
  files,
  models,
  selection,
  pulseId,
  onSelect,
}: DashboardPanelProps) {
  const [downloading, setDownloading] = useState(false);

  const activeFile =
    selection.kind === "file"
      ? files.find((f) => f.id === selection.id)
      : undefined;
  const activeModel =
    selection.kind === "model"
      ? models.find((m) => m.id === selection.id)
      : undefined;

  async function handleDownload() {
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

  const showDownload = Boolean(activeModel || activeFile);

  return (
    <div className="flex h-full min-h-0">
      <aside className="flex w-[20%] min-w-[180px] flex-col border-r border-[var(--border-soft)] bg-[var(--bg-sidebar)]">
        <SidebarSection title="Files">
          {files.length === 0 ? (
            <EmptyHint text="Fetched files will appear here" />
          ) : (
            files.map((file) => (
              <SidebarItem
                key={file.id}
                label={file.name}
                active={selection.kind === "file" && selection.id === file.id}
                pulse={pulseId === file.id}
                onClick={() => onSelect({ kind: "file", id: file.id })}
              />
            ))
          )}
        </SidebarSection>

        <SidebarSection title="Models">
          {models.length === 0 ? (
            <EmptyHint text="Built models will appear here" />
          ) : (
            models.map((model) => (
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
      </aside>

      <main className="flex min-w-0 flex-1 flex-col bg-white">
        {activeModel?.type === "dcf" ? (
          <>
            <ModelHeader name={activeModel.name} showDownload={showDownload} downloading={downloading} onDownload={handleDownload} />
            <div className="min-h-0 flex-1 overflow-hidden">
              <DcfTable model={activeModel.data} />
            </div>
          </>
        ) : activeModel?.type === "comparative" ? (
          <>
            <ModelHeader name={activeModel.name} showDownload={showDownload} downloading={downloading} onDownload={handleDownload} />
            <div className="min-h-0 flex-1 overflow-hidden">
              <ComparativeTable report={activeModel.data} />
            </div>
          </>
        ) : activeFile ? (
          <>
            <ModelHeader name={activeFile.name} showDownload={showDownload} downloading={downloading} onDownload={handleDownload} />
            <div className="min-h-0 flex-1 overflow-hidden">
              <FileViewer file={activeFile} />
            </div>
          </>
        ) : (
          <div className="flex h-full items-center justify-center text-sm text-gray-500">
            Select a file or model from the sidebar
          </div>
        )}
      </main>
    </div>
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
