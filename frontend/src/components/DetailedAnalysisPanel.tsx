import { useMemo, useState } from "react";
import type { FinancialStatements, LineItem, StatementPeriod } from "../types";
import {
  BALANCE_GROUP_LABELS,
  DETAILED_ANALYSIS_DISCLAIMER,
  DETAILED_ANALYSIS_ORDER,
  DETAILED_METRIC_LABELS,
  BANK_SECTOR_DISCLAIMER,
  FCF_FOOTNOTE,
} from "../utils/metricOrder";

const MAX_YEARS = 5;

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
  | { kind: "metric"; key: string; label: string; cells: (LineItem | undefined)[] };

function fmtUsd(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

function cellTitle(item: LineItem | undefined): string {
  if (!item) return "";
  const parts: string[] = [];
  if (item.xbrl_tag) parts.push(`tag: ${item.xbrl_tag}`);
  if (item.source === "derived") parts.push("derived");
  if (item.derived_from?.length) parts.push(`from: ${item.derived_from.join(", ")}`);
  return parts.join(" | ");
}

function periodHeader(p: StatementPeriod): string {
  return `FY${p.fiscal_year}`;
}

function lineValue(p: StatementPeriod, key: string): number | undefined {
  const item = p.line_items.find((li) => li.key === key);
  return item?.value ?? undefined;
}

function accountingEquationOk(p: StatementPeriod): boolean | null {
  const assets = lineValue(p, "total_assets");
  const liabilities = lineValue(p, "total_liabilities");
  const equity = lineValue(p, "stockholders_equity");
  if (assets == null || liabilities == null || equity == null) return null;
  const diff = Math.abs(assets - (liabilities + equity));
  return diff / Math.abs(assets) <= 0.02;
}

function isBankStyle(financials: FinancialStatements): boolean {
  const inc = financials.statements.income?.annual?.[0];
  if (!inc) return false;
  const hasRevenue = inc.line_items.some((li) => li.key === "revenue" && li.value != null);
  const hasCogs = inc.line_items.some(
    (li) => li.key === "cost_of_revenue" && li.value != null,
  );
  const hasGp = inc.line_items.some(
    (li) => li.key === "gross_profit" && li.value != null,
  );
  return hasRevenue && !hasCogs && !hasGp;
}

interface DetailedAnalysisPanelProps {
  financials: FinancialStatements;
}

export default function DetailedAnalysisPanel({
  financials,
}: DetailedAnalysisPanelProps) {
  const scope = (financials.fetch_scope ?? ["income", "balance", "cashflow"]).filter(
    (k): k is StatementKey =>
      k === "income" || k === "balance" || k === "cashflow",
  );
  const [statement, setStatement] = useState<StatementKey>(scope[0] ?? "income");
  const bankStyle = useMemo(() => isBankStyle(financials), [financials]);

  const periods = useMemo(() => {
    const slice = financials.statements[statement];
    if (!slice) return [];
    return slice.annual.slice(0, MAX_YEARS);
  }, [financials, statement]);

  const balancePeriods = useMemo(() => {
    return financials.statements.balance?.annual.slice(0, MAX_YEARS) ?? [];
  }, [financials]);

  const tableRows = useMemo((): TableRow[] => {
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
      const cells = periods.map((p) =>
        p.line_items.find((li) => li.key === key),
      );
      let label = DETAILED_METRIC_LABELS[key] ?? key;
      if (key === "net_cash_change") {
        label = DETAILED_METRIC_LABELS.net_cash_change;
      }
      out.push({
        kind: "metric",
        key,
        label,
        cells,
      });
    }
    return out;
  }, [periods, statement]);

  const hasDetailedData = useMemo(() => {
    for (const stmt of scope) {
      const keys = DETAILED_ANALYSIS_ORDER[stmt] ?? [];
      const annual = financials.statements[stmt]?.annual ?? [];
      for (const p of annual.slice(0, MAX_YEARS)) {
        for (const key of keys) {
          if (p.line_items.some((li) => li.key === key)) return true;
        }
      }
    }
    return false;
  }, [financials, scope]);

  if (!hasDetailedData) {
    return null;
  }

  return (
    <section className="mb-6 rounded-xl border border-indigo-100 bg-white shadow-sm">
      <div className="border-b border-indigo-50 bg-gradient-to-r from-white to-indigo-50/60 px-4 py-3">
        <h2 className="text-sm font-semibold text-gray-900">Detailed Analysis</h2>
        <p className="text-xs text-gray-500">
          Curated 5-year comparison — hover values for XBRL tags
        </p>
      </div>
      <div className="space-y-3 border-b border-amber-100 bg-amber-50/70 px-4 py-3 text-xs leading-relaxed text-amber-950">
        <p>{DETAILED_ANALYSIS_DISCLAIMER}</p>
        {bankStyle && (
          <p className="font-medium text-amber-900">{BANK_SECTOR_DISCLAIMER}</p>
        )}
      </div>
      <div className="p-4">
        <div className="mb-3 flex flex-wrap gap-2">
          {scope.map((key) => (
            <button
              key={key}
              type="button"
              onClick={() => setStatement(key)}
              className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
                statement === key
                  ? "border-indigo-600 bg-indigo-600 text-white"
                  : "border-gray-200 bg-gray-50 text-gray-700 hover:bg-gray-100"
              }`}
            >
              {STATEMENT_TITLES[key]}
            </button>
          ))}
        </div>

        {!periods.length ? (
          <p className="text-sm text-gray-400">No annual periods available.</p>
        ) : (
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
                      {periodHeader(p)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {tableRows.map((row) =>
                  row.kind === "group" ? (
                    <tr key={`group-${row.label}`} className="bg-slate-50">
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
                      {row.cells.map((item, i) => (
                        <td
                          key={`${row.key}-${i}`}
                          title={cellTitle(item)}
                          className={`px-2 py-2 text-right tabular-nums ${
                            item?.value == null ? "text-gray-300" : "text-gray-900"
                          }`}
                        >
                          {item?.value != null ? fmtUsd(item.value) : "n/a"}
                        </td>
                      ))}
                    </tr>
                  ),
                )}
              </tbody>
            </table>
          </div>
        )}

        {statement === "balance" && balancePeriods.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-3 border-t border-gray-100 pt-3 text-xs text-gray-600">
            <span className="font-medium text-gray-700">A = L + E check:</span>
            {balancePeriods.map((p) => {
              const ok = accountingEquationOk(p);
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
        )}

        {statement === "cashflow" && (
          <p className="mt-3 border-t border-gray-100 pt-3 text-xs text-gray-500">
            {FCF_FOOTNOTE}
          </p>
        )}
      </div>
    </section>
  );
}
