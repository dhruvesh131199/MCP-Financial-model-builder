import StatementViewer from "./StatementViewer";

interface FileViewerProps {
  file: import("../types").FileEntry;
  hasDetailedAnalysis?: boolean;
}

export default function FileViewer({
  file,
  hasDetailedAnalysis = false,
}: FileViewerProps) {
  if (file.type === "financials") {
    const ticker = file.data.ticker?.trim() || file.name;
    return (
      <div className="flex h-full flex-col">
        <div className="shrink-0 border-b border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
          <p className="font-medium">SEC data — mapping may be inaccurate</p>
          <p className="mt-1 text-xs leading-relaxed text-amber-900/90">
            These tables were pulled from SEC filings via edgar tools and automatic
            line-item mapping. Tags and labels vary by filer, so amounts here can be
            wrong or incomplete. For higher confidence, connect this workspace to MCP
            and let your host LLM read the official 10-K narrative.
          </p>
          <p className="mt-3 text-xs font-medium text-amber-950">Ask your host LLM</p>
          <blockquote className="mt-1 rounded-md border border-amber-200/80 bg-white/70 px-3 py-2 text-xs leading-relaxed text-gray-700">
            Fetch the latest full 10-K report for {ticker}. Then use{" "}
            <code className="rounded bg-amber-100/80 px-1 text-[11px]">query_rag</code> to
            pull and verify income statement figures (revenue, cost of revenue, gross profit,
            operating income, EBITDA, depreciation and amortization, interest expense,
            income tax, net income), balance sheet figures (cash, total assets, total
            liabilities, stockholders equity, short-term and long-term debt, shares
            outstanding), and cash flow figures (operating cash flow, capital expenditures,
            free cash flow, financing cash flow). Create a reference table of these figures
            for me, then pin the result on my dashboard using{" "}
            <code className="rounded bg-amber-100/80 px-1 text-[11px]">rag_res_on_display</code>.
          </blockquote>
        </div>
        {hasDetailedAnalysis && (
          <p className="border-b border-indigo-100 bg-indigo-50/50 px-4 py-2 text-xs text-indigo-800">
            Curated 5-year Detailed Analysis is available in the{" "}
            <strong>Detailed Analysis</strong> sidebar section for this ticker.
          </p>
        )}
        <StatementViewer financials={file.data} />
      </div>
    );
  }
  return null;
}
