import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getSessionRagChunks, type ChunkPlan } from "../api/sessionRag";
import ChunkExplorer from "../components/rag/ChunkExplorer";

export default function SessionRagChunksPage() {
  const { sessionId, documentId } = useParams<{
    sessionId: string;
    documentId: string;
  }>();
  const [plan, setPlan] = useState<ChunkPlan | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!sessionId || !documentId) return;
    let cancelled = false;
    setLoading(true);
    void getSessionRagChunks(sessionId, documentId)
      .then((p) => {
        if (!cancelled) {
          setPlan(p);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load chunks");
          setPlan(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sessionId, documentId]);

  return (
    <div className="min-h-screen bg-[var(--bg-app)]">
      <header className="border-b border-[var(--border-soft)] bg-white px-4 py-3">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-indigo-600">
              RAG chunk explorer
            </p>
            <h1 className="text-lg font-semibold text-gray-900">
              {plan?.ticker ?? "Document"} {plan?.year ?? ""} · {plan?.doctype ?? ""}
            </h1>
            {documentId && (
              <p className="mt-0.5 font-mono text-xs text-gray-500">{documentId}</p>
            )}
          </div>
          {sessionId && (
            <Link
              to={`/s/${sessionId}`}
              className="text-sm font-medium text-indigo-600 hover:text-indigo-800"
            >
              ← Back to workspace
            </Link>
          )}
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        {loading && <p className="text-sm text-gray-500">Loading chunks…</p>}
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}
        {!loading && !error && plan && (
          <section className="rounded-2xl border-2 border-indigo-200 bg-white p-5 shadow-sm">
            <ChunkExplorer plan={plan} />
          </section>
        )}
      </main>
    </div>
  );
}
