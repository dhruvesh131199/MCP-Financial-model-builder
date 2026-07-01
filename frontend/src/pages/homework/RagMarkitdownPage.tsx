import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  fetchAnnualReportHomework,
  getRagChunks,
  getRagDocument,
  ragRawUrl,
  ragReportUrl,
  uploadDocumentHomework,
  type ChunkPlan,
  type ParentChunk,
  type RagDocumentDetail,
  type RagIngestSummary,
  type SectionOutline,
  type SubChunk,
} from "../../api/homeworkRag";

type ViewTab = "chunks" | "outline";

function fmtNum(n: number): string {
  return n.toLocaleString();
}

function OutlineTable({ outline }: { outline: SectionOutline }) {
  const rows: { label: string; chars: number; tokens: number }[] = [];
  if (outline.preamble) {
    rows.push({
      label: outline.preamble.label,
      chars: outline.preamble.char_count,
      tokens: outline.preamble.approx_tokens,
    });
  }
  for (const item of outline.items) {
    rows.push({
      label: item.label,
      chars: item.char_count,
      tokens: item.approx_tokens,
    });
  }

  const itemCharSum =
    (outline.preamble?.char_count ?? 0) +
    outline.items.reduce((s, i) => s + i.char_count, 0);

  return (
    <div>
      {outline.warnings.length > 0 && (
        <ul className="mb-3 list-disc pl-5 text-xs text-amber-700">
          {outline.warnings.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}
      <div className="overflow-x-auto rounded-lg border border-gray-200">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wide text-gray-500">
            <tr>
              <th className="px-3 py-2 font-semibold">Section</th>
              <th className="px-3 py-2 text-right font-semibold">Characters</th>
              <th className="px-3 py-2 text-right font-semibold">~Tokens</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row, i) => (
              <tr key={`${row.label}-${i}`}>
                <td className="px-3 py-2 font-medium text-gray-900">{row.label}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.chars)}</td>
                <td className="px-3 py-2 text-right tabular-nums">{fmtNum(row.tokens)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-gray-500">
        Item rows sum: {fmtNum(itemCharSum)} chars · document total:{" "}
        {fmtNum(outline.total_chars)} chars · ~Tokens ≈ chars ÷ 4
      </p>
    </div>
  );
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

const PREVIEW_CHARS = 240;

function approxTokens(chars: number): number {
  return Math.round(chars / 4);
}

function contentPreview(content: string): string {
  if (content.length <= PREVIEW_CHARS) return content;
  return `${content.slice(0, PREVIEW_CHARS)}…`;
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

function ChunkExplorer({ plan }: { plan: ChunkPlan }) {
  const [openParent, setOpenParent] = useState<string | null>(
    plan.parent_chunks[0]?.id ?? null,
  );
  const cfg = plan.config;

  if (plan.parent_chunks.length === 0) {
    return (
      <p className="text-sm text-amber-700">
        No parent chunks found. Re-fetch the 10-K with the API server running the latest code.
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
        <span className="font-medium text-gray-800">{plan.subchunk_count}</span> sub-chunk(s) ·
        parent max {cfg.parent_max_chars?.toLocaleString()} / overlap {cfg.parent_overlap} · sub{" "}
        {cfg.subchunk_size} / overlap {cfg.subchunk_overlap}
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
                  Parent chunk
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

export default function RagMarkitdownPage() {
  const [ticker, setTicker] = useState("AAPL");
  const [uploadTicker, setUploadTicker] = useState("AAPL");
  const [uploadYear, setUploadYear] = useState(String(new Date().getFullYear()));
  const [uploadDoctype, setUploadDoctype] = useState("10K");
  const [sessionId, setSessionId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chunkError, setChunkError] = useState<string | null>(null);
  const [summary, setSummary] = useState<RagIngestSummary | null>(null);
  const [detail, setDetail] = useState<RagDocumentDetail | null>(null);
  const [chunkPlan, setChunkPlan] = useState<ChunkPlan | null>(null);
  const [viewTab, setViewTab] = useState<ViewTab>("chunks");
  const [chunksLoading, setChunksLoading] = useState(false);
  const explorerRef = useRef<HTMLElement>(null);

  const sid = sessionId.trim() || undefined;
  const outline = detail?.section_outline ?? summary?.section_outline ?? null;
  const docId = summary?.document_id;

  async function loadChunks(documentId: string) {
    setChunksLoading(true);
    setChunkError(null);
    try {
      const chunks = await getRagChunks(documentId, sid);
      setChunkPlan(chunks);
      setViewTab("chunks");
      requestAnimationFrame(() => {
        explorerRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      });
    } catch (err) {
      setChunkPlan(null);
      setChunkError(err instanceof Error ? err.message : "Failed to load chunks");
    } finally {
      setChunksLoading(false);
    }
  }

  async function loadDetail(doc: RagIngestSummary) {
    const d = await getRagDocument(doc.document_id, sid);
    setDetail(d);
    await loadChunks(doc.document_id);
  }

  async function handleFetch() {
    setError(null);
    setChunkError(null);
    setLoading(true);
    try {
      const result = await fetchAnnualReportHomework(ticker.trim(), sid);
      setSummary(result);
      await loadDetail(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Fetch failed");
      setSummary(null);
      setDetail(null);
      setChunkPlan(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(file: File) {
    setError(null);
    setChunkError(null);
    setLoading(true);
    const year = parseInt(uploadYear, 10);
    if (!uploadTicker.trim() || Number.isNaN(year)) {
      setError("Upload requires a valid ticker and year");
      setLoading(false);
      return;
    }
    try {
      const result = await uploadDocumentHomework(file, {
        ticker: uploadTicker.trim(),
        year,
        doctype: uploadDoctype,
        sessionId: sid,
      });
      setSummary(result);
      await loadDetail(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
      setSummary(null);
      setDetail(null);
      setChunkPlan(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[var(--bg-app)]">
      <header className="border-b border-[var(--border-soft)] bg-white px-4 py-4">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
              Homework lab
            </p>
            <h1 className="text-xl font-semibold text-gray-900">Annual report → chunks</h1>
            <p className="mt-1 text-sm text-gray-600">
              Fetch a 10-K, then explore parent + sub-chunks for RAG sizing.
            </p>
          </div>
          <Link to="/" className="text-sm text-gray-500 hover:text-gray-900">
            ← Home
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-5xl space-y-6 px-4 py-6">
        <section className="rounded-2xl border border-[var(--border-soft)] bg-white p-5 shadow-sm">
          <h2 className="text-sm font-semibold text-gray-900">Optional session</h2>
          <p className="mt-1 text-xs text-gray-500">
            Leave blank for homework-only output folders; paste a session UUID to store under{" "}
            <code className="rounded bg-gray-100 px-1">data/sessions/…/documents/</code>
          </p>
          <input
            type="text"
            value={sessionId}
            onChange={(e) => setSessionId(e.target.value)}
            placeholder="session UUID (optional)"
            className="mt-2 w-full rounded-lg border border-gray-200 px-3 py-2 text-sm"
          />
        </section>

        <div className="grid gap-6 md:grid-cols-2">
          <section className="rounded-2xl border border-[var(--border-soft)] bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-900">SEC fetch (MCP path)</h2>
            <p className="mt-1 text-xs text-gray-500">Latest primary 10-K — PDF if attached, else HTML.</p>
            <div className="mt-3 flex gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm uppercase"
                placeholder="Ticker"
              />
              <button
                type="button"
                disabled={loading || !ticker.trim()}
                onClick={() => void handleFetch()}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {loading ? "Working…" : "Fetch 10-K"}
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-[var(--border-soft)] bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-gray-900">Manual upload</h2>
            <p className="mt-1 text-xs text-gray-500">
              PDF, HTML, or other formats MarkItDown supports. Ticker, year, and doctype are required
              for chunk IDs.
            </p>
            <div className="mt-3 grid gap-2 sm:grid-cols-3">
              <input
                type="text"
                value={uploadTicker}
                onChange={(e) => setUploadTicker(e.target.value.toUpperCase())}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm uppercase"
                placeholder="Ticker"
                disabled={loading}
              />
              <input
                type="number"
                value={uploadYear}
                onChange={(e) => setUploadYear(e.target.value)}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
                placeholder="Year"
                min={1990}
                max={2100}
                disabled={loading}
              />
              <select
                value={uploadDoctype}
                onChange={(e) => setUploadDoctype(e.target.value)}
                className="rounded-lg border border-gray-200 px-3 py-2 text-sm"
                disabled={loading}
              >
                <option value="10K">10K</option>
              </select>
            </div>
            <label className="mt-3 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 px-4 py-8 text-sm text-gray-600 hover:border-indigo-300 hover:bg-indigo-50/30">
              <span>{loading ? "Converting…" : "Choose file or drop here"}</span>
              <input
                type="file"
                className="hidden"
                accept=".pdf,.html,.htm,.docx,.doc,.txt"
                disabled={loading}
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) void handleUpload(f);
                }}
              />
            </label>
          </section>
        </div>

        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {summary && (
          <section className="rounded-2xl border border-[var(--border-soft)] bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-gray-900">Result</h2>
                <p className="mt-1 font-mono text-xs text-gray-500">{summary.document_id}</p>
              </div>
              <div className="flex flex-wrap gap-2">
                {docId && (
                  <a
                    href={ragRawUrl(docId, sid)}
                    target="_blank"
                    rel="noreferrer"
                    className="rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Open original filing
                  </a>
                )}
                <a
                  href={ragReportUrl(summary.document_id, sid)}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-lg border border-gray-200 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
                >
                  report.html (item table only)
                </a>
              </div>
            </div>
            <dl className="mt-4 grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-gray-500">Markdown</dt>
                <dd className="font-medium">{summary.markdown_chars.toLocaleString()} chars</dd>
              </div>
              <div>
                <dt className="text-gray-500">Items</dt>
                <dd className="font-medium">{summary.items_found ?? 0}</dd>
              </div>
              <div>
                <dt className="text-gray-500">Chunks</dt>
                <dd className="font-medium">
                  {summary.parent_count ?? 0} parent · {summary.subchunk_count ?? 0} sub
                </dd>
              </div>
            </dl>
          </section>
        )}

        {summary && (
          <section
            ref={explorerRef}
            className="rounded-2xl border-2 border-indigo-200 bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-base font-semibold text-gray-900">Chunk visualization</h2>
              <div className="flex rounded-lg border border-gray-200 p-0.5 text-xs">
                <button
                  type="button"
                  onClick={() => setViewTab("chunks")}
                  className={`rounded-md px-3 py-1.5 font-medium ${
                    viewTab === "chunks"
                      ? "bg-indigo-600 text-white"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Parent & sub-chunks
                </button>
                <button
                  type="button"
                  onClick={() => setViewTab("outline")}
                  className={`rounded-md px-3 py-1.5 font-medium ${
                    viewTab === "outline"
                      ? "bg-indigo-600 text-white"
                      : "text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  Item summary table
                </button>
              </div>
            </div>

            {viewTab === "chunks" && (
              <div className="mt-4">
                {chunksLoading && (
                  <p className="text-sm text-gray-500">Loading chunks…</p>
                )}
                {chunkError && (
                  <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
                    {chunkError}
                    {docId && (
                      <button
                        type="button"
                        className="ml-2 font-medium text-indigo-600 underline"
                        onClick={() => void loadChunks(docId)}
                      >
                        Retry
                      </button>
                    )}
                    <p className="mt-2 text-xs">
                      Re-fetch the 10-K if this is an older run without chunks.json. Ensure the
                      API server is running latest code.
                    </p>
                  </div>
                )}
                {!chunksLoading && !chunkError && chunkPlan && (
                  <ChunkExplorer plan={chunkPlan} />
                )}
                {!chunksLoading && !chunkError && !chunkPlan && (
                  <p className="text-sm text-gray-500">No chunk data yet.</p>
                )}
              </div>
            )}

            {viewTab === "outline" && outline && (
              <div className="mt-4">
                <OutlineTable outline={outline} />
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
