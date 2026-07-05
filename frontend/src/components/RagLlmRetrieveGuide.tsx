import { useCallback } from "react";
import { Link } from "react-router-dom";

function CopyIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      stroke="currentColor"
      strokeWidth={1.75}
      aria-hidden
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
      />
    </svg>
  );
}

function CopyPrompt({ text, label }: { text: string; label: string }) {
  const handleCopy = useCallback(() => {
    void navigator.clipboard.writeText(text);
  }, [text]);

  return (
    <div className="group relative rounded-lg border border-gray-200/80 bg-white px-3 py-2.5 pr-10">
      <p className="text-[10px] font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-1 font-mono text-[13px] leading-relaxed text-gray-800">{text}</p>
      <button
        type="button"
        onClick={handleCopy}
        title="Copy to clipboard"
        aria-label={`Copy ${label}`}
        className="absolute right-2 top-2 rounded-md p-1.5 text-gray-400 transition hover:bg-indigo-50 hover:text-indigo-600"
      >
        <CopyIcon className="h-4 w-4" />
      </button>
    </div>
  );
}

export default function RagLlmRetrieveGuide({ sessionId }: { sessionId: string }) {
  const startPrompt = `Start my session with session id ${sessionId}`;
  const examplePrompt =
    "Get me the risks from the AAPL 10-K using query_rag (ticker AAPL on first retrieve).";

  return (
    <section className="mt-4 rounded-xl border border-indigo-200/80 bg-gradient-to-br from-indigo-50/80 to-white p-4 shadow-sm">
      <h3 className="text-sm font-semibold text-gray-900">
        Wanna retrieve information using LLM?
      </h3>
      <p className="mt-1 text-xs leading-relaxed text-gray-600">
        Ingest a 10-K below, then use Cursor, Claude, or another MCP host to query it with{" "}
        <span className="font-mono text-indigo-700">query_rag</span>.
      </p>

      <ol className="mt-4 space-y-4 text-sm text-gray-700">
        <li className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
            1
          </span>
          <div className="min-w-0 flex-1">
            <p>
              If you have not connected your host LLM yet,{" "}
              <Link
                to="/setup"
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-indigo-600 underline decoration-indigo-300 underline-offset-2 hover:text-indigo-800"
              >
                connect Cursor or Claude
              </Link>
              .
            </p>
          </div>
        </li>

        <li className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
            2
          </span>
          <div className="min-w-0 flex-1 space-y-2">
            <p>After connecting, paste this in chat to attach this workspace:</p>
            <CopyPrompt text={startPrompt} label="Start session" />
          </div>
        </li>

        <li className="flex gap-3">
          <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-indigo-100 text-xs font-semibold text-indigo-700">
            3
          </span>
          <div className="min-w-0 flex-1 space-y-2">
            <p>Then ask your question. Example (pass ticker on first retrieve; answers should include Sources):</p>
            <CopyPrompt text={examplePrompt} label="Example question" />
          </div>
        </li>
      </ol>
    </section>
  );
}
