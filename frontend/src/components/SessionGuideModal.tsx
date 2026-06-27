import { useEffect, useRef } from "react";

export interface SessionGuideModalProps {
  open: boolean;
  onClose: () => void;
}

const EXAMPLES = [
  {
    id: "fetch",
    title: "Fetch SEC financials",
    description: "Pull official 10-K / 10-Q data into your workspace. Results appear in Files.",
    prompt: "Fetch Apple SEC financial reports.",
    accent: "from-emerald-500/15 to-teal-500/5",
    icon: (
      <svg className="h-5 w-5 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    id: "detailed-analysis",
    title: "Ask for detailed analysis (Under development)",
    description:
      "Curated 5-year income, balance, and cash flow report — appears in Detailed Analysis.",
    prompt: "Do a detailed analysis of Micron.",
    accent: "from-sky-500/15 to-cyan-500/5",
    icon: (
      <svg className="h-5 w-5 text-sky-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
    ),
  },
  {
    id: "comps-2",
    title: "Peer comparison (2 companies)",
    description: "Side-by-side fundamentals, margins, and market multiples.",
    prompt: "Build a comparative analysis report for Visa and Mastercard.",
    accent: "from-violet-500/15 to-purple-500/5",
    icon: (
      <svg className="h-5 w-5 text-violet-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
      </svg>
    ),
  },
  {
    id: "comps-3",
    title: "Peer comparison (3 companies)",
    description: "Benchmark a basket of peers in one report.",
    prompt: "Build a comparative analysis for Apple, Microsoft, and Google.",
    accent: "from-indigo-500/15 to-blue-500/5",
    icon: (
      <svg className="h-5 w-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
      </svg>
    ),
  },
  {
    id: "dcf",
    title: "DCF valuation model",
    description: "Dashboard editor — ask forecast years in chat, fill assumptions on the dashboard, click Update.",
    prompt: "Build a 5-year DCF model for Micron (MU). Ask me how many forecast years if needed.",
    accent: "from-amber-500/15 to-orange-500/5",
    icon: (
      <svg className="h-5 w-5 text-amber-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
      </svg>
    ),
  },
] as const;

function PromptCard({ prompt }: { prompt: string }) {
  return (
    <div className="group relative mt-3 rounded-xl border border-gray-200/80 bg-gray-50/80 px-3.5 py-3">
      <p className="pr-8 font-mono text-[13px] leading-relaxed text-gray-800">{prompt}</p>
      <CopyButton text={prompt} />
    </div>
  );
}

function CopyButton({ text }: { text: string }) {
  return (
    <button
      type="button"
      title="Copy prompt"
      onClick={() => void navigator.clipboard.writeText(text)}
      className="absolute right-2 top-2 rounded-lg p-1.5 text-gray-400 opacity-0 transition hover:bg-white hover:text-indigo-600 group-hover:opacity-100"
    >
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.75}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
    </button>
  );
}

export default function SessionGuideModal({ open, onClose }: SessionGuideModalProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;

    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }

    document.addEventListener("keydown", onKeyDown);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = "";
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6">
      <button
        type="button"
        aria-label="Close guide"
        className="absolute inset-0 bg-gray-900/50 backdrop-blur-sm"
        onClick={onClose}
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="session-guide-title"
        className="relative flex max-h-[min(90vh,820px)] w-full max-w-2xl flex-col overflow-hidden rounded-2xl border border-white/20 bg-white shadow-2xl shadow-indigo-900/20"
      >
        <div className="relative shrink-0 overflow-hidden border-b border-indigo-100 bg-gradient-to-br from-indigo-600 via-indigo-600 to-violet-700 px-6 py-6 text-white sm:px-8">
          <div className="absolute -right-8 -top-8 h-32 w-32 rounded-full bg-white/10 blur-2xl" />
          <div className="absolute -bottom-6 left-1/3 h-24 w-24 rounded-full bg-violet-400/20 blur-xl" />
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="absolute right-4 top-4 rounded-lg p-1.5 text-white/80 transition hover:bg-white/15 hover:text-white"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <p className="text-xs font-semibold uppercase tracking-widest text-indigo-200">Your workspace is ready</p>
          <h2 id="session-guide-title" className="mt-1 text-2xl font-semibold tracking-tight sm:text-[1.65rem]">
            What to try next
          </h2>
          <p className="mt-2 max-w-lg text-sm leading-relaxed text-indigo-100/95">
            Chat with your assistant using the MCP tools — fetched files and built models show up here
            automatically. Copy any prompt below and paste it into your chat.
          </p>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-6 py-5 sm:px-8">
          <div className="grid gap-4 sm:grid-cols-2">
            {EXAMPLES.map((ex) => (
              <article
                key={ex.id}
                className={`rounded-xl border border-gray-100 bg-gradient-to-br ${ex.accent} p-4 shadow-sm`}
              >
                <div className="flex items-start gap-3">
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white shadow-sm">
                    {ex.icon}
                  </div>
                  <div className="min-w-0">
                    <h3 className="text-sm font-semibold text-gray-900">{ex.title}</h3>
                    <p className="mt-0.5 text-xs leading-relaxed text-gray-600">{ex.description}</p>
                  </div>
                </div>
                <PromptCard prompt={ex.prompt} />
              </article>
            ))}
          </div>

          <p className="mt-5 text-center text-xs text-gray-500">
            New files and models appear in the sidebar as your assistant runs tools.
          </p>
        </div>

        <div className="shrink-0 border-t border-gray-100 bg-gray-50/80 px-6 py-4 sm:px-8">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-indigo-600/25 transition hover:bg-indigo-700"
          >
            Got it — start exploring
          </button>
        </div>
      </div>
    </div>
  );
}

export function SessionGuideButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition hover:from-indigo-700 hover:to-violet-700 hover:shadow-indigo-500/40"
    >
      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-white/20">
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
      </span>
      Try these in chat
    </button>
  );
}
