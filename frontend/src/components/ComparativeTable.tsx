import type { ReactNode } from "react";
import type { ComparativeReport } from "../types";

function fmtNum(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (Math.abs(n) >= 1e6) return `${(n / 1e6).toFixed(2)}M`;
  if (Math.abs(n) >= 1e3) return `${(n / 1e3).toFixed(2)}K`;
  return n.toFixed(2);
}

function fmtPct(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${(n * 100).toFixed(1)}%`;
}

function fmtRatio(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `${n.toFixed(2)}x`;
}

function fmtPrice(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return `$${n.toFixed(2)}`;
}

interface RowDef {
  label: string;
  fieldKey?: string;
  get: (row: ComparativeReport["companies"][0]) => string;
  section: "fundamentals" | "multiples";
}

export const COMPARATIVE_ROWS: RowDef[] = [
  { label: "Revenue", fieldKey: "revenue", section: "fundamentals", get: (r) => fmtNum(r.fundamentals.revenue) },
  { label: "Net income", fieldKey: "net_income", section: "fundamentals", get: (r) => fmtNum(r.fundamentals.net_income) },
  { label: "Net margin", fieldKey: "net_margin", section: "fundamentals", get: (r) => fmtPct(r.fundamentals.net_margin) },
  {
    label: "Rev growth YoY",
    fieldKey: "revenue_growth_yoy",
    section: "fundamentals",
    get: (r) => fmtPct(r.fundamentals.revenue_growth_yoy),
  },
  { label: "ROE", fieldKey: "roe", section: "fundamentals", get: (r) => fmtPct(r.fundamentals.roe) },
  { label: "FCF margin", fieldKey: "fcf_margin", section: "fundamentals", get: (r) => fmtPct(r.fundamentals.fcf_margin) },
  { label: "Stock price", fieldKey: "stock_price", section: "multiples", get: (r) => fmtPrice(r.multiples.stock_price) },
  { label: "Market cap", fieldKey: "market_cap_usd", section: "multiples", get: (r) => fmtNum(r.multiples.market_cap_usd) },
  {
    label: "Market EV",
    fieldKey: "market_enterprise_value",
    section: "multiples",
    get: (r) => fmtNum(r.multiples.market_enterprise_value),
  },
  { label: "P/E", fieldKey: "pe_ratio", section: "multiples", get: (r) => fmtRatio(r.multiples.pe_ratio) },
  { label: "P/B", fieldKey: "pb_ratio", section: "multiples", get: (r) => fmtRatio(r.multiples.pb_ratio) },
  { label: "EV / Sales", fieldKey: "ev_to_sales", section: "multiples", get: (r) => fmtRatio(r.multiples.ev_to_sales) },
  { label: "EV / EBITDA", fieldKey: "ev_to_ebitda", section: "multiples", get: (r) => fmtRatio(r.multiples.ev_to_ebitda) },
];

function cellHint(
  company: ComparativeReport["companies"][0],
  fieldKey: string | undefined,
  display: string,
): string | undefined {
  if (display !== "—" || !fieldKey) return undefined;
  const st = company.fundamentals.field_status?.[fieldKey];
  if (st?.reason) return st.reason;
  if (company.market_data.errors?.length && fieldKey.startsWith("pe")) {
    return company.market_data.errors.join("; ");
  }
  return undefined;
}

interface ComparativeTableProps {
  report: ComparativeReport;
}

function formatTickerList(tickers: string[]): string {
  if (tickers.length === 0) return "these companies";
  if (tickers.length === 1) return tickers[0];
  if (tickers.length === 2) return `${tickers[0]} and ${tickers[1]}`;
  return `${tickers.slice(0, -1).join(", ")}, and ${tickers[tickers.length - 1]}`;
}

export default function ComparativeTable({ report }: ComparativeTableProps) {
  const companies = report.companies;
  const tickers = companies.map((c) => c.ticker);
  const priceAsOf = companies.find((c) => c.market_data.as_of)?.market_data.as_of;

  let lastSection: string | null = null;
  const bodyRows: ReactNode[] = [];

  for (const row of COMPARATIVE_ROWS) {
    if (row.section !== lastSection) {
      lastSection = row.section;
      bodyRows.push(
        <tr key={`section-${row.section}`} className="bg-gray-50">
          <td
            colSpan={companies.length + 1}
            className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500"
          >
            {row.section === "fundamentals" ? "Fundamentals (SEC)" : "Market multiples"}
          </td>
        </tr>,
      );
    }
    bodyRows.push(
      <tr key={row.label} className="border-t border-gray-100 hover:bg-gray-50/50">
        <td className="sticky left-0 z-10 bg-white px-3 py-2 font-medium text-gray-700">
          {row.label}
        </td>
        {companies.map((c) => {
          const display = row.get(c);
          const hint = cellHint(c, row.fieldKey, display);
          const isNa = c.fundamentals.field_status?.[row.fieldKey ?? ""]?.status === "not_applicable";
          return (
            <td
              key={c.ticker}
              title={hint}
              className={`px-3 py-2 tabular-nums ${c.is_target ? "bg-indigo-50/40 font-medium" : ""} ${
                display === "—" ? (isNa ? "text-gray-300" : "text-amber-600/90") : ""
              }`}
            >
              {display}
            </td>
          );
        })}
      </tr>,
    );
  }

  return (
    <div className="flex h-full flex-col overflow-auto p-4">
      <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50/90 px-4 py-3 text-sm text-amber-950">
        <p className="font-medium">SEC data — mapping may be inaccurate</p>
        <p className="mt-1 text-xs leading-relaxed text-amber-900/90">
          These figures were pulled from SEC filings via edgar tools and automatic
          line-item mapping. Tags and labels vary by filer, so amounts here can be
          wrong or incomplete. For higher confidence, connect this workspace to MCP
          and let your host LLM read the official 10-K narrative.
        </p>
        <p className="mt-3 text-xs font-medium text-amber-950">Ask your host LLM</p>
        <blockquote className="mt-1 rounded-md border border-amber-200/80 bg-white/70 px-3 py-2 text-xs leading-relaxed text-gray-700">
          For {formatTickerList(tickers)}: fetch the latest full 10-K for each company. Use{" "}
          <code className="rounded bg-amber-100/80 px-1 text-[11px]">query_rag</code> to pull the
          metrics in this comparison — revenue, net income, margins, revenue growth, ROE, FCF, and
          valuation multiples — then pin a side-by-side table on my dashboard with{" "}
          <code className="rounded bg-amber-100/80 px-1 text-[11px]">rag_res_on_display</code>.
        </blockquote>
      </div>

      <div className="mb-4">
        <h2 className="text-lg font-semibold text-gray-900">Peer comparison</h2>
        <p className="text-sm text-gray-500">
          FY{report.fiscal_year_used}
          {report.fiscal_year_note ? ` — ${report.fiscal_year_note}` : ""}
        </p>
        {priceAsOf && (
          <p className="text-xs text-gray-400">
            Market prices as of {priceAsOf.slice(0, 10)} (Finnhub)
          </p>
        )}
        {report.market_data_errors && report.market_data_errors.length > 0 && (
          <div className="mt-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
            <p className="font-medium">Market data unavailable</p>
            <ul className="mt-1 list-inside list-disc text-amber-800">
              {companies
                .filter((c) => report.market_data_errors?.includes(c.ticker))
                .map((c) => (
                  <li key={c.ticker}>
                    {c.ticker}: {c.market_data.errors?.join("; ") || "Finnhub fetch failed"}
                  </li>
                ))}
            </ul>
          </div>
        )}
      </div>

      <div className="overflow-x-auto rounded-lg border border-[var(--border-soft)]">
        <table className="min-w-full text-left text-xs">
          <thead className="bg-indigo-50/60 text-indigo-900">
            <tr>
              <th className="sticky left-0 z-10 bg-indigo-50/95 px-3 py-2 font-semibold">Metric</th>
              {companies.map((c) => (
                <th
                  key={c.ticker}
                  className={`px-3 py-2 font-semibold whitespace-nowrap ${
                    c.is_target ? "bg-indigo-100" : ""
                  }`}
                >
                  {c.company_name || c.ticker}
                  {c.is_target && (
                    <span className="ml-1 rounded bg-indigo-600 px-1 py-0.5 text-[10px] text-white">
                      Target
                    </span>
                  )}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>{bodyRows}</tbody>
        </table>
      </div>

      <SummaryStrip summary={report.summary} />
    </div>
  );
}

function SummaryStrip({ summary }: { summary: ComparativeReport["summary"] }) {
  const items = [
    ["Peer median P/E", summary.peer_median_pe, false],
    ["Peer median EV/Sales", summary.peer_median_ev_to_sales, false],
    ["Peer median EV/EBITDA", summary.peer_median_ev_to_ebitda, false],
    ["Peer median net margin", summary.peer_median_net_margin, true],
  ] as const;

  return (
    <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
      {items.map(([label, val, isPct]) => (
        <div
          key={label}
          className="rounded-lg border border-[var(--border-soft)] bg-gradient-to-br from-white to-indigo-50/30 px-3 py-2"
        >
          <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
          <div className="text-sm font-semibold text-indigo-900">
            {isPct ? fmtPct(val as number | null) : fmtRatio(val as number | null)}
          </div>
        </div>
      ))}
    </div>
  );
}

export { fmtNum, fmtPct, fmtRatio };
