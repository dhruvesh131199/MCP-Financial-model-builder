import { useRef, useState } from "react";
import type { RagDisplayModelEntry } from "../types";
import { exportRagResultPdf } from "../utils/exportRagResultPdf";
import MarkdownWithCitations from "./MarkdownWithCitations";

interface RagDisplayViewerProps {
  entry: RagDisplayModelEntry;
  sessionId: string;
}

export default function RagDisplayViewer({ entry, sessionId }: RagDisplayViewerProps) {
  const articleRef = useRef<HTMLElement>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  function handleExportPdf() {
    const el = articleRef.current;
    if (!el) return;
    setExporting(true);
    setExportError(null);
    try {
      exportRagResultPdf(entry.name, el.innerHTML);
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="flex shrink-0 items-center justify-between gap-3 border-b border-[var(--border-soft)] bg-gradient-to-r from-white to-violet-50/40 px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-base font-semibold text-violet-950">{entry.name}</h2>
          <p className="text-xs text-gray-500">Pinned from chat · RAG reference</p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            type="button"
            onClick={handleExportPdf}
            disabled={exporting}
            className="rounded-lg border border-violet-200/80 bg-white px-3 py-1.5 text-xs font-medium text-violet-700 shadow-sm transition hover:border-violet-300 hover:bg-violet-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export PDF"}
          </button>
          {exportError ? (
            <p className="max-w-[14rem] text-right text-[10px] text-red-600">{exportError}</p>
          ) : null}
        </div>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        <article
          ref={articleRef}
          className="rag-display-prose mx-auto max-w-4xl text-sm text-gray-800"
        >
          <MarkdownWithCitations
            markdown={entry.data.content_md}
            sessionId={sessionId}
          />
        </article>
      </div>
    </div>
  );
}
