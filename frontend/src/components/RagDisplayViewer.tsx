import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { RagDisplayModelEntry } from "../types";

interface RagDisplayViewerProps {
  entry: RagDisplayModelEntry;
}

export default function RagDisplayViewer({ entry }: RagDisplayViewerProps) {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <header className="shrink-0 border-b border-[var(--border-soft)] bg-gradient-to-r from-white to-violet-50/40 px-4 py-3">
        <h2 className="text-base font-semibold text-violet-950">{entry.name}</h2>
        <p className="text-xs text-gray-500">Pinned from chat · RAG reference</p>
      </header>
      <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5">
        <article className="rag-display-prose mx-auto max-w-4xl text-sm text-gray-800">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{entry.data.content_md}</ReactMarkdown>
        </article>
      </div>
    </div>
  );
}
