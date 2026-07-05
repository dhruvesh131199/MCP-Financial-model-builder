import { useCallback } from "react";

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

export default function SessionIdCopy({
  sessionId,
  showCopyAlways = false,
}: {
  sessionId: string;
  showCopyAlways?: boolean;
}) {
  const handleCopy = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      void navigator.clipboard.writeText(sessionId);
    },
    [sessionId],
  );

  return (
    <div className="group inline-flex items-center gap-1 rounded-md border border-gray-200/80 bg-gray-50/80 py-1 pl-2.5 pr-1.5">
      <p className="whitespace-nowrap font-mono text-[11px] leading-snug text-gray-600">
        <span className="font-sans text-gray-500">Session id:</span> {sessionId}
      </p>
      <button
        type="button"
        onClick={handleCopy}
        title="Copy session id"
        aria-label="Copy session id"
        className={`shrink-0 rounded p-0.5 text-gray-400 transition hover:text-gray-600 ${
          showCopyAlways ? "opacity-100" : "opacity-0 group-hover:opacity-100"
        }`}
      >
        <CopyIcon className="h-3.5 w-3.5" />
      </button>
    </div>
  );
}
