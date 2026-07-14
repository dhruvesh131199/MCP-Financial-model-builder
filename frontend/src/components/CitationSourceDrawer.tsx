import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  getSessionRagParent,
  type RagParentChunkResponse,
} from "../api/sessionRag";
import { highlightQuoteInElement } from "../lib/citeHighlight";

export interface CitationSourceDrawerProps {
  sessionId: string;
  parentId: string;
  quote?: string;
  onClose: () => void;
}

const ANIM_MS = 280;

/**
 * Right slide-over showing a parent chunk for an inline citation chip.
 */
export default function CitationSourceDrawer({
  sessionId,
  parentId,
  quote,
  onClose,
}: CitationSourceDrawerProps) {
  const [entered, setEntered] = useState(false);
  const [closing, setClosing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [parent, setParent] = useState<RagParentChunkResponse | null>(null);
  const [quoteFound, setQuoteFound] = useState<boolean | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const id = window.requestAnimationFrame(() => setEntered(true));
    return () => window.cancelAnimationFrame(id);
  }, []);

  function requestClose() {
    if (closing) return;
    setClosing(true);
    window.setTimeout(onClose, ANIM_MS);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      setClosing((already) => {
        if (already) return already;
        window.setTimeout(onClose, ANIM_MS);
        return true;
      });
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setParent(null);
    setQuoteFound(null);
    void getSessionRagParent(sessionId, parentId)
      .then((row) => {
        if (!cancelled) setParent(row);
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load source");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, parentId]);

  useEffect(() => {
    if (!parent || !bodyRef.current) return;
    const q = quote?.trim();
    if (!q) {
      setQuoteFound(null);
      return;
    }

    let cancelled = false;
    const run = () => {
      if (cancelled || !bodyRef.current) return;
      const mark = highlightQuoteInElement(bodyRef.current, q);
      setQuoteFound(Boolean(mark));
      if (mark) {
        mark.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    };

    // Wait a frame so ReactMarkdown has painted text nodes
    const id = window.requestAnimationFrame(() => {
      window.requestAnimationFrame(run);
    });
    return () => {
      cancelled = true;
      window.cancelAnimationFrame(id);
    };
  }, [parent, quote]);

  const open = entered && !closing;
  const quoteLabel = quote?.trim();

  return createPortal(
    <div className="fixed inset-0 z-50 flex justify-end" role="presentation">
      <button
        type="button"
        className={`absolute inset-0 bg-gray-900/35 backdrop-blur-[1px] transition-opacity duration-300 ease-out ${
          open ? "opacity-100" : "opacity-0"
        }`}
        aria-label="Close source drawer"
        onClick={requestClose}
      />
      <aside
        className={`relative flex h-full w-full max-w-lg flex-col border-l border-gray-200 bg-gradient-to-b from-stone-50 to-white shadow-2xl transition-transform duration-300 ease-out ${
          open ? "translate-x-0" : "translate-x-full"
        }`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="citation-drawer-title"
      >
        <header className="flex shrink-0 items-start justify-between gap-3 border-b border-gray-200/90 bg-white/90 px-4 py-3 backdrop-blur-sm">
          <div className="min-w-0">
            <p className="text-[10px] font-medium uppercase tracking-wide text-gray-500">
              Source excerpt
            </p>
            <h3
              id="citation-drawer-title"
              className="mt-0.5 truncate text-sm font-semibold text-gray-900"
              title={parent?.label ?? parentId}
            >
              {parent?.label ?? parentId}
            </h3>
            {parent ? (
              <p className="mt-0.5 text-[11px] text-gray-500">
                {parent.ticker} · {parent.doctype} · FY{parent.year} · section #
                {parent.chunk_index}
              </p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={requestClose}
            className="shrink-0 rounded-md px-2 py-1 text-sm text-gray-500 hover:bg-gray-100 hover:text-gray-900"
          >
            Close
          </button>
        </header>

        {quoteLabel ? (
          <div className="shrink-0 border-b border-amber-100 bg-amber-50/80 px-4 py-2.5">
            <p className="text-[10px] font-medium uppercase tracking-wide text-amber-800/80">
              Looking for
            </p>
            <p className="mt-0.5 text-xs leading-relaxed text-amber-950">
              <span className="italic">“{quoteLabel}”</span>
              {quoteFound === false ? (
                <span className="ml-1.5 not-italic text-amber-700/90">
                  — not found in this section; showing full excerpt
                </span>
              ) : null}
            </p>
          </div>
        ) : null}

        <div ref={scrollRef} className="min-h-0 flex-1 overflow-y-auto px-5 py-5">
          {loading ? (
            <p className="text-sm text-gray-500">Loading source…</p>
          ) : error ? (
            <p className="text-sm text-red-600">{error}</p>
          ) : parent ? (
            <div
              ref={bodyRef}
              className="rag-display-prose cite-source-prose max-w-none text-sm text-gray-800"
            >
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{parent.content}</ReactMarkdown>
            </div>
          ) : (
            <p className="text-sm text-gray-500">No content.</p>
          )}
        </div>
      </aside>
    </div>,
    document.body,
  );
}
