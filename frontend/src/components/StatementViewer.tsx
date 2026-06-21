import { useMemo, useState } from "react";
import type { FinancialStatements, StatementPeriod } from "../types";

type StatementKey = "income" | "balance" | "cashflow";
type PeriodType = "annual" | "quarterly";
type ViewMode = "compare" | "single";

const STATEMENT_LABELS: Record<StatementKey, string> = {
  income: "Income",
  balance: "Balance Sheet",
  cashflow: "Cash Flow",
};

function fmtDisplay(value: number, unit: string): string {
  if (unit === "USD/shares") return `$${value.toFixed(2)}`;
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

interface StatementViewerProps {
  financials: FinancialStatements;
}

export default function StatementViewer({ financials }: StatementViewerProps) {
  const scope = (financials.fetch_scope ?? ["income", "balance", "cashflow"]).filter(
    (k): k is StatementKey =>
      k === "income" || k === "balance" || k === "cashflow",
  );
  const [statement, setStatement] = useState<StatementKey>(
    scope[0] ?? "income",
  );
  const [periodType, setPeriodType] = useState<PeriodType>("annual");
  const [viewMode, setViewMode] = useState<ViewMode>("compare");
  const [periodIndex, setPeriodIndex] = useState(0);

  const periods = useMemo(() => {
    const slice = financials.statements[statement];
    if (!slice) return [];
    const list = periodType === "annual" ? slice.annual : slice.quarterly;
    return list.slice(0, periodType === "annual" ? 5 : 8);
  }, [financials, statement, periodType]);

  const activePeriod: StatementPeriod | undefined = periods[periodIndex];

  const comparison = useMemo(() => {
    if (!periods.length) return { labels: [] as string[], cells: [] as string[][] };
    const keys = periods[0].line_items.map((li) => li.key);
    const labels = periods[0].line_items.map((li) => li.label);
    const cells = keys.map((key) =>
      periods.map((p) => {
        const item = p.line_items.find((li) => li.key === key);
        return item ? fmtDisplay(item.value, item.unit) : "—";
      }),
    );
    return { labels, cells };
  }, [periods]);

  function handleStatement(next: StatementKey) {
    setStatement(next);
    setPeriodIndex(0);
  }

  function handlePeriodType(next: PeriodType) {
    setPeriodType(next);
    setPeriodIndex(0);
    setViewMode(next === "annual" ? "compare" : "single");
  }

  const periodHeaders = periods.map(
    (p) => `FY${p.fiscal_year} ${p.fiscal_period}`,
  );

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white">
      <div className="shrink-0 border-b border-[var(--border-soft)] bg-gradient-to-r from-indigo-50/50 to-violet-50/40 px-4 py-3">
        <h3 className="text-sm font-semibold text-indigo-900/90">
          {financials.entity_name}{" "}
          <span className="font-normal text-indigo-500">
            ({financials.ticker})
          </span>
        </h3>
        <p className="mt-0.5 text-xs text-gray-500">
          SEC EDGAR · {new Date(financials.fetched_at).toLocaleDateString()}
          {scope.length < 3 && (
            <span className="text-violet-500">
              {" "}
              · {scope.map((s) => STATEMENT_LABELS[s]).join(", ")}
            </span>
          )}
        </p>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2 border-b border-[var(--border-soft)] px-4 py-2">
        <TabGroup>
          {scope.map((key) => (
            <TabButton
              key={key}
              active={statement === key}
              onClick={() => handleStatement(key)}
            >
              {STATEMENT_LABELS[key]}
            </TabButton>
          ))}
        </TabGroup>
        <span className="mx-1 text-gray-300">|</span>
        <TabGroup>
          <TabButton
            active={periodType === "annual"}
            onClick={() => handlePeriodType("annual")}
          >
            Annual
          </TabButton>
          <TabButton
            active={periodType === "quarterly"}
            onClick={() => handlePeriodType("quarterly")}
          >
            Quarterly
          </TabButton>
        </TabGroup>
        {periodType === "annual" && periods.length > 1 && (
          <>
            <span className="mx-1 text-gray-300">|</span>
            <TabGroup>
              <TabButton
                active={viewMode === "compare"}
                onClick={() => setViewMode("compare")}
              >
                5Y Compare
              </TabButton>
              <TabButton
                active={viewMode === "single"}
                onClick={() => setViewMode("single")}
              >
                Single
              </TabButton>
            </TabGroup>
          </>
        )}
        {viewMode === "single" && periods.length > 0 && (
          <>
            <span className="mx-1 text-gray-300">|</span>
            <select
              value={periodIndex}
              onChange={(e) => setPeriodIndex(Number(e.target.value))}
              className="rounded-lg border border-indigo-100 bg-white px-2 py-1 text-xs text-indigo-800 focus:border-indigo-300 focus:outline-none"
            >
              {periods.map((p, i) => (
                <option key={`${p.fiscal_year}-${p.fiscal_period}`} value={i}>
                  FY{p.fiscal_year} {p.fiscal_period}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {periods.length === 0 ? (
          <p className="text-sm text-gray-400">
            No {periodType} data for this statement.
          </p>
        ) : viewMode === "compare" && periodType === "annual" ? (
          <ComparisonTable
            headers={periodHeaders}
            labels={comparison.labels}
            cells={comparison.cells}
            periods={periods}
          />
        ) : activePeriod && activePeriod.line_items.length > 0 ? (
          <SinglePeriodTable period={activePeriod} />
        ) : (
          <p className="text-sm text-gray-400">No line items for this period.</p>
        )}
      </div>
    </div>
  );
}

function ComparisonTable({
  headers,
  labels,
  cells,
  periods,
}: {
  headers: string[];
  labels: string[];
  cells: string[][];
  periods: StatementPeriod[];
}) {
  return (
    <>
      <table className="w-full min-w-[480px] border-collapse text-sm">
        <thead>
          <tr className="border-b-2 border-indigo-100 text-left text-xs font-semibold uppercase tracking-wide text-indigo-400">
            <th className="sticky left-0 z-10 bg-white py-2 pr-4">Line Item</th>
            {headers.map((h) => (
              <th key={h} className="px-2 py-2 text-right whitespace-nowrap">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {labels.map((label, ri) => (
            <tr
              key={label}
              className="border-b border-gray-50 hover:bg-indigo-50/30"
            >
              <td className="sticky left-0 z-10 bg-white py-2 pr-4 text-gray-700">
                {label}
              </td>
              {cells[ri].map((cell, ci) => (
                <td
                  key={ci}
                  className="px-2 py-2 text-right font-medium tabular-nums text-gray-900"
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {periods[0]?.filed && (
        <p className="mt-4 text-xs text-gray-400">
          Annual comparison · up to {periods.length} years · SEC XBRL
        </p>
      )}
    </>
  );
}

function SinglePeriodTable({ period }: { period: StatementPeriod }) {
  return (
    <>
      <table className="w-full max-w-lg border-collapse text-sm">
        <thead>
          <tr className="border-b-2 border-indigo-100 text-left text-xs font-semibold uppercase tracking-wide text-indigo-400">
            <th className="py-2 pr-4">Line Item</th>
            <th className="py-2 text-right">
              FY{period.fiscal_year} {period.fiscal_period}
            </th>
          </tr>
        </thead>
        <tbody>
          {period.line_items.map((item) => (
            <tr
              key={item.key}
              className="border-b border-gray-50 hover:bg-indigo-50/30"
            >
              <td className="py-2 pr-4 text-gray-700">{item.label}</td>
              <td className="py-2 text-right font-medium tabular-nums text-gray-900">
                {fmtDisplay(item.value, item.unit)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {period.filed && (
        <p className="mt-4 text-xs text-gray-400">
          Filed {period.filed}
          {period.form ? ` · ${period.form}` : ""}
        </p>
      )}
    </>
  );
}

function TabGroup({ children }: { children: React.ReactNode }) {
  return <div className="flex gap-1">{children}</div>;
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-2.5 py-1 text-xs font-medium transition ${
        active
          ? "bg-indigo-100 text-indigo-700"
          : "text-gray-500 hover:bg-violet-50 hover:text-indigo-600"
      }`}
    >
      {children}
    </button>
  );
}
