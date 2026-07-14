import { useMemo, useRef, useState } from "react";
import type { DetailedAnalysisData, DetailedMetricCell } from "../types";
import TrendAnalysisSection from "./TrendAnalysisSection";
import { exportRagResultPdf } from "../utils/exportRagResultPdf";
import {
  BALANCE_GROUP_LABELS,
  DETAILED_ANALYSIS_DISCLAIMER,
  DETAILED_ANALYSIS_ORDER,
  DETAILED_METRIC_LABELS,
  BANK_SECTOR_DISCLAIMER,
  FCF_FOOTNOTE,
} from "../utils/metricOrder";
import MarkdownWithCitations from "./MarkdownWithCitations";

const MAX_YEARS = 5;

const NARRATIVE_SECTION_ORDER = [
  "gross_profit",
  "return_on_capital",
  "earnings_per_share",
  "cash_flow",
] as const;

type StatementKey = "income" | "balance" | "cashflow";

const STATEMENT_TITLES: Record<StatementKey, string> = {
  income: "Income Statement",
  balance: "Balance Sheet",
  cashflow: "Cash Flow",
};

const NET_CASH_TOOLTIP =
  "Net change in cash = movement during the fiscal year. Cash at period end = balance sheet position on the last day of the fiscal year.";

type TableRow =
  | { kind: "group"; label: string }
  | { kind: "metric"; key: string; label: string; cells: (DetailedMetricCell | undefined)[] };

function fmtUsd(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

function cellTitle(cell: DetailedMetricCell | undefined): string {
  if (!cell) return "";
  const parts: string[] = [];
  if (cell.xbrl_tag) parts.push(`tag: ${cell.xbrl_tag}`);
  if (cell.row_label) parts.push(`row: ${cell.row_label}`);
  if (cell.source === "derived") parts.push("derived");
  if (cell.warning) parts.push(`⚠ ${cell.warning}`);
  return parts.join(" | ");
}

function cellsForKey(
  periods: DetailedAnalysisData["periods"],
  statement: StatementKey,
  key: string,
): (DetailedMetricCell | undefined)[] {
  return periods.map((p) => {
    const list =
      statement === "income"
        ? p.income
        : statement === "balance"
          ? p.balance
          : p.cashflow;
    return list.find((c) => c.key === key);
  });
}

function buildTableRows(
  periods: DetailedAnalysisData["periods"],
  statement: StatementKey,
): TableRow[] {
  const keys = DETAILED_ANALYSIS_ORDER[statement] ?? [];
  const out: TableRow[] = [];
  let lastGroup: string | undefined;
  for (const key of keys) {
    const group =
      statement === "balance" ? BALANCE_GROUP_LABELS[key] : undefined;
    if (group && group !== lastGroup) {
      out.push({ kind: "group", label: group });
      lastGroup = group;
    }
    out.push({
      kind: "metric",
      key,
      label: DETAILED_METRIC_LABELS[key] ?? key,
      cells: cellsForKey(periods, statement, key),
    });
  }
  return out;
}

interface DetailedAnalysisViewerProps {
  analysis: DetailedAnalysisData;
  sessionId: string;
}

export default function DetailedAnalysisViewer({
  analysis,
  sessionId,
}: DetailedAnalysisViewerProps) {
  const exportRef = useRef<HTMLDivElement>(null);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);

  const periods = useMemo(
    () =>
      [...analysis.periods]
        .sort((a, b) => b.fiscal_year - a.fiscal_year)
        .slice(0, MAX_YEARS),
    [analysis.periods],
  );

  if (!periods.length) {
    return (
      <p className="text-sm text-gray-400">No periods in detailed analysis.</p>
    );
  }

  const yearCount = periods.length;
  const exportTitle = `${analysis.ticker} detailed analysis — last ${yearCount} ${
    yearCount === 1 ? "year" : "years"
  }`;

  function handleExportPdf() {
    const el = exportRef.current;
    if (!el) return;
    setExporting(true);
    setExportError(null);
    try {
      exportRagResultPdf(
        exportTitle,
        el.innerHTML,
        `${analysis.entity_name} · SEC EDGAR · Detailed Analysis · Financial Analyzer`,
      );
    } catch (err) {
      setExportError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-start justify-between gap-3 border-b border-indigo-50 bg-gradient-to-r from-white to-indigo-50/60 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-gray-900">{exportTitle}</h2>
          <p className="mt-0.5 text-xs text-gray-500">
            {analysis.entity_name} · SEC EDGAR ·{" "}
            {new Date(analysis.fetched_at).toLocaleDateString()}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1">
          <button
            type="button"
            onClick={handleExportPdf}
            disabled={exporting}
            className="rounded-lg border border-indigo-200/80 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 shadow-sm transition hover:border-indigo-300 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {exporting ? "Exporting…" : "Export PDF"}
          </button>
          {exportError ? (
            <p className="max-w-[14rem] text-right text-[10px] text-red-600">
              {exportError}
            </p>
          ) : null}
        </div>
      </div>

      <div className="space-y-3 border-b border-amber-100 bg-amber-50/70 px-4 py-3 text-xs leading-relaxed text-amber-950">
        <p>{DETAILED_ANALYSIS_DISCLAIMER}</p>
        {analysis.is_bank_style && (
          <p className="font-medium text-amber-900">{BANK_SECTOR_DISCLAIMER}</p>
        )}
      </div>

      <div className="min-h-0 flex-1 overflow-auto p-4">
        <div ref={exportRef}>
        <p className="mb-6 text-sm font-medium text-gray-700">
          {yearCount}-year overview
        </p>

        <DetailedStatementSection
          title={STATEMENT_TITLES.income}
          periods={periods}
          statement="income"
        />

        <DetailedStatementSection
          title={STATEMENT_TITLES.balance}
          periods={periods}
          statement="balance"
          footer={
            <div className="mt-3 flex flex-wrap gap-3 border-t border-gray-100 pt-3 text-xs text-gray-600">
              <span className="font-medium text-gray-700">A = L + E check:</span>
              {periods.map((p) => {
                const ok = p.accounting_equation_ok;
                return (
                  <span
                    key={`eq-${p.fiscal_year}`}
                    className={
                      ok === true
                        ? "text-emerald-700"
                        : ok === false
                          ? "text-amber-700"
                          : "text-gray-400"
                    }
                  >
                    FY{p.fiscal_year}{" "}
                    {ok === true ? "✓" : ok === false ? "⚠ mismatch" : "n/a"}
                  </span>
                );
              })}
            </div>
          }
        />

        <DetailedStatementSection
          title={STATEMENT_TITLES.cashflow}
          periods={periods}
          statement="cashflow"
          footer={
            <p className="mt-3 border-t border-gray-100 pt-3 text-xs text-gray-500">
              {FCF_FOOTNOTE}
            </p>
          }
        />

        {analysis.trend_analysis && (
          <TrendAnalysisSection trend={analysis.trend_analysis} />
        )}

        {(() => {
          const narratives = analysis.narratives ?? [];
          const ordered = NARRATIVE_SECTION_ORDER.map((key) =>
            narratives.find((n) => n.section_key === key),
          ).filter((n): n is NonNullable<typeof n> => Boolean(n?.content_md));
          if (!ordered.length) return null;
          return (
            <div className="mt-10 space-y-6 border-t border-indigo-100 pt-8">
              <h3 className="text-sm font-semibold text-gray-900">
                Narrative analysis (10-K)
              </h3>
              {ordered.map((n) => (
                <section
                  key={n.section_key}
                  className="mt-2 border-t border-gray-200 pt-5"
                >
                  <h4 className="mb-3 border-b border-gray-200 pb-2 text-sm font-semibold text-gray-900">
                    {n.title}
                  </h4>
                  <article className="rag-display-prose max-w-4xl text-sm text-gray-800">
                    <MarkdownWithCitations
                      markdown={n.content_md}
                      sessionId={sessionId}
                    />
                  </article>
                </section>
              ))}
            </div>
          );
        })()}

        {analysis.integrity_checks.length > 0 && (
          <div className="mt-6 rounded-lg border border-amber-200 bg-amber-50/50 px-3 py-2 text-xs text-amber-900">
            <p className="font-medium">Integrity notes</p>
            <ul className="mt-1 list-inside list-disc">
              {analysis.integrity_checks.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}
        </div>
      </div>
    </div>
  );
}

function DetailedStatementSection({
  title,
  periods,
  statement,
  footer,
}: {
  title: string;
  periods: DetailedAnalysisData["periods"];
  statement: StatementKey;
  footer?: React.ReactNode;
}) {
  const tableRows = useMemo(
    () => buildTableRows(periods, statement),
    [periods, statement],
  );

  return (
    <section className="mb-10">
      <h3 className="mb-3 border-b border-gray-200 pb-2 text-sm font-semibold text-gray-900">
        {title}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500">
              <th className="py-2 pr-3 text-left font-medium">Line item</th>
              {periods.map((p) => (
                <th
                  key={`${p.fiscal_year}-${p.period_end}`}
                  className="px-2 py-2 text-right font-medium tabular-nums"
                >
                  FY{p.fiscal_year}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row) =>
              row.kind === "group" ? (
                <tr key={`group-${statement}-${row.label}`} className="bg-slate-50">
                  <td
                    colSpan={periods.length + 1}
                    className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-slate-500"
                  >
                    {row.label}
                  </td>
                </tr>
              ) : (
                <tr
                  key={row.key}
                  className="border-b border-gray-100 hover:bg-gray-50/80"
                >
                  <td
                    className="py-2 pr-3 font-medium text-gray-800"
                    title={
                      row.key === "net_cash_change" ? NET_CASH_TOOLTIP : undefined
                    }
                  >
                    {row.label}
                  </td>
                  {row.cells.map((cell, i) => (
                    <td
                      key={`${row.key}-${i}`}
                      title={cellTitle(cell)}
                      className={`px-2 py-2 text-right tabular-nums ${
                        cell?.value == null ? "text-gray-300" : "text-gray-900"
                      }`}
                    >
                      {cell?.value != null ? fmtUsd(cell.value) : "n/a"}
                    </td>
                  ))}
                </tr>
              ),
            )}
          </tbody>
        </table>
      </div>
      {footer}
    </section>
  );
}
