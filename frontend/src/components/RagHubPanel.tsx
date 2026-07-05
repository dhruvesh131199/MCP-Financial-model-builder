import { useEffect, useRef, useState } from "react";
import {
  fetchSessionRag,
  isRagInFlight,
  sessionRagChunksPath,
  sessionRagRawHref,
  subscribeRagInFlight,
  uploadSessionRag,
  type RagDocumentEntry,
} from "../api/sessionRag";
import { ragDocumentDisplayLabel } from "../lib/ragDocumentLabel";
import RagLlmRetrieveGuide from "./RagLlmRetrieveGuide";

type IngestTab = "fetch" | "upload";

interface RagHubPanelProps {
  sessionId: string;
  documents: RagDocumentEntry[];
  onRefresh: () => void;
}

export default function RagHubPanel({
  sessionId,
  documents,
  onRefresh,
}: RagHubPanelProps) {
  const [tab, setTab] = useState<IngestTab>("fetch");
  const [ticker, setTicker] = useState("AAPL");
  const [fetchYear, setFetchYear] = useState("");
  const [uploadTicker, setUploadTicker] = useState("AAPL");
  const [uploadYear, setUploadYear] = useState(String(new Date().getFullYear()));
  const [uploadDoctype, setUploadDoctype] = useState("10K");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [loading, setLoading] = useState(() => isRagInFlight(sessionId));
  const [banner, setBanner] = useState<string | null>(null);

  useEffect(() => {
    const sync = () => setLoading(isRagInFlight(sessionId));
    sync();
    return subscribeRagInFlight(sync);
  }, [sessionId]);

  async function handleFetch() {
    setBanner(null);
    const year = fetchYear.trim() ? parseInt(fetchYear, 10) : undefined;
    if (fetchYear.trim() && Number.isNaN(year)) {
      setBanner("Enter a valid fiscal year or leave blank for latest");
      return;
    }
    try {
      const result = await fetchSessionRag(sessionId, ticker.trim(), year);
      if (result.success) {
        const note = result.from_cache ? " (loaded from library — no re-download)" : "";
        setBanner(`Linked ${result.filing_key ?? ticker}${note}`);
      } else {
        setBanner(result.error ?? "Fetch failed");
      }
      onRefresh();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Fetch failed");
      onRefresh();
    }
  }

  async function handleUpload() {
    if (!selectedFile) {
      setBanner("Choose a file first");
      return;
    }
    const year = parseInt(uploadYear, 10);
    if (!uploadTicker.trim() || Number.isNaN(year)) {
      setBanner("Upload requires a valid ticker and year");
      return;
    }
    setBanner(null);
    try {
      const result = await uploadSessionRag(sessionId, selectedFile, {
        ticker: uploadTicker.trim(),
        year,
        doctype: uploadDoctype,
      });
      if (result.success) {
        const note = result.from_cache ? " (loaded from library)" : "";
        setBanner(`Linked ${result.filing_key ?? selectedFile.name}${note}`);
        setSelectedFile(null);
        if (fileInputRef.current) fileInputRef.current.value = "";
      } else {
        setBanner(result.error ?? "Upload failed");
      }
      onRefresh();
    } catch (err) {
      setBanner(err instanceof Error ? err.message : "Upload failed");
      onRefresh();
    }
  }

  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="border-b border-[var(--border-soft)] bg-gradient-to-r from-white to-indigo-50/40 px-4 py-3">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-gray-900">
            Upload financial document for your questions!
          </h2>
          <span className="rounded bg-indigo-600 px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wide text-white">
            RAG
          </span>
        </div>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-gray-600">
          Fetch or upload an annual report (10-K). Your host retrieves the right sections from
          this filing and uses them as context—so answers stay grounded in the document, not
          guessed from memory.
        </p>
        <RagLlmRetrieveGuide sessionId={sessionId} />
      </div>

      <div className="flex-1 space-y-6 p-4">
        <div className="flex rounded-lg border border-gray-200 p-0.5 text-xs w-fit">
          <button
            type="button"
            onClick={() => setTab("fetch")}
            className={`rounded-md px-3 py-1.5 font-medium ${
              tab === "fetch" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            Fetch 10-K
          </button>
          <button
            type="button"
            onClick={() => setTab("upload")}
            className={`rounded-md px-3 py-1.5 font-medium ${
              tab === "upload" ? "bg-indigo-600 text-white" : "text-gray-600 hover:bg-gray-50"
            }`}
          >
            Upload
          </button>
        </div>

        {tab === "fetch" && (
          <div className="max-w-md">
            <p className="text-xs text-gray-500">
              Primary 10-K from SEC (PDF or HTML). Leave year blank for latest.
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <input
                type="text"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                className="min-w-[100px] flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm uppercase"
                placeholder="Ticker"
                disabled={loading}
              />
              <input
                type="number"
                value={fetchYear}
                onChange={(e) => setFetchYear(e.target.value)}
                className="w-28 rounded-lg border border-gray-200 px-3 py-2 text-sm"
                placeholder="FY year"
                min={1990}
                max={2100}
                disabled={loading}
              />
              <button
                type="button"
                disabled={loading || !ticker.trim()}
                onClick={() => void handleFetch()}
                className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                {loading ? "Working…" : "Fetch"}
              </button>
            </div>
          </div>
        )}

        {tab === "upload" && (
          <div className="max-w-lg">
            <p className="text-xs text-gray-500">
              PDF, HTML, or other formats MarkItDown supports.
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-3">
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
            <label className="mt-3 flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 px-4 py-6 text-sm text-gray-600 hover:border-indigo-300">
              <span>{selectedFile ? selectedFile.name : "Choose file"}</span>
              <input
                ref={fileInputRef}
                type="file"
                className="hidden"
                accept=".pdf,.html,.htm,.docx,.doc,.txt"
                disabled={loading}
                onChange={(e) => {
                  setSelectedFile(e.target.files?.[0] ?? null);
                }}
              />
            </label>
            <button
              type="button"
              disabled={
                loading || !selectedFile || !uploadTicker.trim() || Number.isNaN(parseInt(uploadYear, 10))
              }
              onClick={() => void handleUpload()}
              className="mt-3 rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {loading ? "Uploading…" : "Upload file"}
            </button>
          </div>
        )}

        {banner && (
          <div
            className={`rounded-lg border px-4 py-3 text-sm ${
              banner.includes("failed") || banner.includes("requires") || banner.includes("valid")
                ? "border-red-200 bg-red-50 text-red-700"
                : "border-indigo-200 bg-indigo-50 text-indigo-800"
            }`}
          >
            {banner}
          </div>
        )}

        <section>
          <h3 className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Your session documents
          </h3>
          {documents.length === 0 ? (
            <p className="mt-2 text-sm text-gray-400">No documents linked yet.</p>
          ) : (
            <ul className="mt-3 space-y-2">
              {documents.map((doc) => (
                <li
                  key={doc.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-gray-900">
                      {ragDocumentDisplayLabel(doc)}
                    </p>
                    <p className="font-mono text-[10px] text-gray-400">{doc.filing_key}</p>
                    {doc.status === "error" && doc.error && (
                      <p className="mt-1 text-xs text-red-600">{doc.error}</p>
                    )}
                    {doc.from_cache && doc.status === "ready" && (
                      <p className="mt-0.5 text-[10px] text-indigo-600">Loaded from library</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {doc.status === "ready" && (
                      <>
                        <span className="rounded-full bg-green-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-green-800">
                          Done
                        </span>
                        {doc.document_id && (
                          <>
                            <a
                              href={sessionRagChunksPath(sessionId, doc.document_id)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="rounded-lg border border-indigo-200 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                            >
                              View chunks
                            </a>
                            {sessionRagRawHref(sessionId, doc) && (
                              <a
                                href={sessionRagRawHref(sessionId, doc)!}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="rounded-lg border border-indigo-200 px-2 py-1 text-xs font-medium text-indigo-700 hover:bg-indigo-50"
                              >
                                View 10-K
                              </a>
                            )}
                          </>
                        )}
                      </>
                    )}
                    {doc.status === "error" && (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-[10px] font-semibold uppercase text-red-800">
                        Error
                      </span>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
