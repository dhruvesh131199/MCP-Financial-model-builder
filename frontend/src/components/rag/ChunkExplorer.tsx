import { useState } from "react";
import type { ChunkPlan, ParentChunk, SubChunk } from "../../api/sessionRag";

const PREVIEW_CHARS = 240;

function approxTokens(chars: number): number {
  return Math.round(chars / 4);
}

function contentPreview(content: string): string {
  if (content.length <= PREVIEW_CHARS) return content;
  return `${content.slice(0, PREVIEW_CHARS)}…`;
}

function ReadMoreModal({
  title,
  text,
  onClose,
}: {
  title: string;
  text: string;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
      onKeyDown={(e) => e.key === "Escape" && onClose()}
      role="presentation"
    >
      <div
        className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-xl bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-labelledby="chunk-modal-title"
      >
        <div className="flex items-center justify-between border-b border-gray-200 px-4 py-3">
          <h3 id="chunk-modal-title" className="text-sm font-semibold text-gray-900">
            {title}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-gray-500 hover:text-gray-900"
          >
            Close
          </button>
        </div>
        <pre className="max-h-[calc(80vh-3.5rem)] overflow-auto whitespace-pre-wrap p-4 text-xs leading-relaxed text-gray-800">
          {text}
        </pre>
      </div>
    </div>
  );
}

function ChunkCard({
  title,
  charCount,
  tokens,
  content,
  nested,
}: {
  title: string;
  charCount: number;
  tokens: number;
  content: string;
  nested?: boolean;
}) {
  const [modal, setModal] = useState(false);
  const preview = contentPreview(content);
  return (
    <div
      className={`rounded-lg border p-3 ${
        nested
          ? "ml-3 border-dashed border-indigo-200 bg-indigo-50/40"
          : "border-indigo-200 bg-indigo-50/60"
      }`}
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="text-sm font-semibold text-gray-900">{title}</p>
        <p className="text-xs text-gray-500">
          {charCount.toLocaleString()} chars · ~{tokens.toLocaleString()} tokens
        </p>
      </div>
      <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-gray-600">{preview}</p>
      <button
        type="button"
        onClick={() => setModal(true)}
        className="mt-2 text-xs font-medium text-indigo-600 hover:text-indigo-800"
      >
        Read more
      </button>
      {modal && <ReadMoreModal title={title} text={content} onClose={() => setModal(false)} />}
    </div>
  );
}

export default function ChunkExplorer({ plan }: { plan: ChunkPlan }) {
  const [openParent, setOpenParent] = useState<string | null>(
    plan.parent_chunks[0]?.id ?? null,
  );
  const cfg = plan.config ?? {};

  if (plan.parent_chunks.length === 0) {
    return (
      <p className="text-sm text-amber-700">
        No parent chunks found for this filing.
      </p>
    );
  }

  return (
    <div>
      {plan.warnings.length > 0 && (
        <ul className="mb-3 list-disc pl-5 text-xs text-amber-700">
          {plan.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <p className="mb-4 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600">
        <span className="font-medium text-gray-800">{plan.parent_count}</span> parent chunk(s) ·{" "}
        <span className="font-medium text-gray-800">{plan.subchunk_count}</span> sub-chunk(s)
        {cfg.parent_max_chars != null && (
          <>
            {" "}
            · parent max {cfg.parent_max_chars.toLocaleString()} / overlap{" "}
            {cfg.parent_overlap} · sub {cfg.subchunk_size} / overlap {cfg.subchunk_overlap}
          </>
        )}
      </p>
      <div className="space-y-4">
        {plan.parent_chunks.map((parent: ParentChunk) => {
          const expanded = openParent === parent.id;
          return (
            <div
              key={parent.id}
              className="overflow-hidden rounded-xl border-2 border-indigo-100 bg-white shadow-sm"
            >
              <button
                type="button"
                className="flex w-full items-center justify-between gap-2 border-b border-indigo-50 bg-indigo-50/50 px-4 py-2 text-left"
                onClick={() => setOpenParent(expanded ? null : parent.id)}
              >
                <span className="text-xs font-semibold uppercase tracking-wide text-indigo-700">
                  {parent.item_label ?? `Parent chunk #${parent.chunk_index}`}
                </span>
                <span className="text-xs text-indigo-600">
                  {expanded ? "▼ Hide sub-chunks" : "▶ Show sub-chunks"} (
                  {parent.subchunks.length})
                </span>
              </button>
              <div className="p-3">
                <ChunkCard
                  title={parent.id}
                  charCount={parent.char_count}
                  tokens={parent.approx_tokens}
                  content={parent.content}
                />
              </div>
              {expanded && parent.subchunks.length > 0 && (
                <div className="space-y-2 border-t border-indigo-100 bg-white px-3 pb-3 pt-2">
                  <p className="text-xs font-medium text-gray-500">Sub-chunks (RAG embed units)</p>
                  {parent.subchunks.map((sub: SubChunk) => (
                    <ChunkCard
                      key={sub.id}
                      title={sub.id.slice(0, 8)}
                      charCount={sub.content.length}
                      tokens={approxTokens(sub.content.length)}
                      content={sub.content}
                      nested
                    />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
