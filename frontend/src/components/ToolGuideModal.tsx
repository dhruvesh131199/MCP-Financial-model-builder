import { useEffect, useRef } from "react";
import { MCP_TOOL_GUIDE, MCP_TOOL_GUIDE_EXAMPLE_NOTE } from "../config/mcpToolGuide";

export interface ToolGuideModalProps {
  open: boolean;
  onClose: () => void;
}

function ToolsIcon({ className }: { className?: string }) {
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
        d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l4.655-5.653m4.31-4.31l1.414-1.414a2 2 0 112.828 2.828l-1.414 1.414m-4.31-4.31l4.31 4.31"
      />
    </svg>
  );
}

export function ToolGuideButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-indigo-600 to-violet-600 px-3 py-2 text-xs font-medium text-white transition hover:from-indigo-700 hover:to-violet-700"
    >
      <ToolsIcon className="h-3.5 w-3.5 shrink-0" />
      Tools guide
    </button>
  );
}

export default function ToolGuideModal({ open, onClose }: ToolGuideModalProps) {
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
        aria-label="Close tool guide"
        className="absolute inset-0 bg-gray-900/40 backdrop-blur-[2px]"
        onClick={onClose}
      />

      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tool-guide-title"
        className="relative flex max-h-[min(90vh,720px)] w-full max-w-3xl flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-xl"
      >
        <div className="flex shrink-0 items-start justify-between gap-3 border-b border-gray-100 px-5 py-4 sm:px-6">
          <div className="flex items-start gap-3">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-gray-100 text-gray-600">
              <ToolsIcon className="h-5 w-5" />
            </div>
            <div>
              <h2 id="tool-guide-title" className="text-base font-semibold text-gray-900">
                MCP tools guide
              </h2>
              <p className="mt-0.5 text-xs text-gray-500">
                Copy an example into Cursor or Claude chat. Pass{" "}
                <code className="rounded bg-gray-100 px-1">session_id</code> on every call after
                your workspace is started.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
          >
            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 sm:px-6">
          <div className="overflow-x-auto rounded-xl border border-gray-200">
            <table className="min-w-full border-collapse text-left text-xs">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-3 py-2.5 font-semibold text-gray-600">Tool</th>
                  <th className="px-3 py-2.5 font-semibold text-gray-600">What it does</th>
                  <th className="min-w-[220px] px-3 py-2.5 font-semibold text-gray-600">
                    <span>Example prompts</span>
                    <p className="mt-1 font-normal text-[10px] leading-snug text-gray-500">
                      {MCP_TOOL_GUIDE_EXAMPLE_NOTE}
                    </p>
                  </th>
                </tr>
              </thead>
              <tbody>
                {MCP_TOOL_GUIDE.map((row, idx) => (
                  <tr
                    key={row.tool}
                    className={idx % 2 === 0 ? "bg-white" : "bg-gray-50/50"}
                  >
                    <td className="align-top px-3 py-3 font-mono text-[11px] font-medium text-indigo-700">
                      {row.tool}
                    </td>
                    <td className="align-top px-3 py-3 leading-relaxed text-gray-700">
                      {row.summary}
                    </td>
                    <td className="align-top px-3 py-3">
                      <ul className="space-y-1.5">
                        {row.examples.filter(Boolean).map((ex) => (
                          <li
                            key={ex}
                            className="rounded-md border border-gray-100 bg-white px-2 py-1.5 text-[11px] leading-relaxed text-gray-800"
                          >
                            {ex}
                          </li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="shrink-0 border-t border-gray-100 bg-gray-50/80 px-5 py-3 sm:px-6">
          <button
            type="button"
            onClick={onClose}
            className="w-full rounded-lg border border-gray-200 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
