import { useMemo, useState } from "react";
import type { CoverageEntry, FinancialStatements, LineItem, StatementPeriod } from "../types";
import { METRIC_LABELS, STATEMENT_METRIC_ORDER } from "../utils/metricOrder";

const MAX_ANNUAL_PERIODS = 5;
const MAX_QUARTERLY_PERIODS = 20;

function periodHeader(p: StatementPeriod): string {
  if (p.period_end) {
    const d = new Date(`${p.period_end}T12:00:00`);
    const short = Number.isNaN(d.getTime())
      ? p.period_end
      : d.toLocaleDateString(undefined, { month: "short", year: "numeric" });
    return `${p.fiscal_period} ${short}`;
  }
  return `FY${p.fiscal_year} ${p.fiscal_period}`;
}

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
  const hasQuarterlyData = useMemo(() => {
    return Object.values(financials.statements).some(
      (slice) => (slice?.quarterly.length ?? 0) > 0,
    );
  }, [financials.statements]);

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
    const cap = periodType === "annual" ? MAX_ANNUAL_PERIODS : MAX_QUARTERLY_PERIODS;
    return list.slice(0, cap);
  }, [financials, statement, periodType]);

  const effectiveViewMode: ViewMode =
    periods.length > 1 ? viewMode : "single";

  const activePeriod: StatementPeriod | undefined = periods[periodIndex];

  const comparison = useMemo(() => {
    if (!periods.length) {
      return {
        labels: [] as string[],
        cells: [] as string[][],
        items: [] as (LineItem | undefined)[][],
        keys: [] as string[],
      };
    }
    const order = STATEMENT_METRIC_ORDER[statement] ?? [];
    const presentKeys = new Set(
      periods.flatMap((p) => p.line_items.map((li) => li.key)),
    );
    const keys = [
      ...order,
      ...[...presentKeys].filter((k) => !order.includes(k)),
    ];
    const labels = keys.map((k) => METRIC_LABELS[k] ?? k);
    const itemsByRow = keys.map((key) =>
      periods.map((p) => p.line_items.find((li) => li.key === key)),
    );
    const cells = itemsByRow.map((row) =>
      row.map((item) => (item ? fmtDisplay(item.value, item.unit) : "—")),
    );
    return { labels, cells, items: itemsByRow, keys };
  }, [periods, statement]);

  function handleStatement(next: StatementKey) {
    setStatement(next);
    setPeriodIndex(0);
  }

  function handlePeriodType(next: PeriodType) {
    setPeriodType(next);
    setPeriodIndex(0);
    setViewMode("compare");
  }

  const periodHeaders = periods.map(periodHeader);
  const compareLabel =
    periodType === "annual"
      ? `${Math.min(periods.length, MAX_ANNUAL_PERIODS)}Y Compare`
      : `${Math.min(periods.length, MAX_QUARTERLY_PERIODS)}Q Compare`;

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
          {hasQuarterlyData && (
            <TabButton
              active={periodType === "quarterly"}
              onClick={() => handlePeriodType("quarterly")}
            >
              Quarterly
            </TabButton>
          )}
        </TabGroup>
        {periods.length > 1 && (
          <>
            <span className="mx-1 text-gray-300">|</span>
            <TabGroup>
              <TabButton
                active={viewMode === "compare"}
                onClick={() => setViewMode("compare")}
              >
                {compareLabel}
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
        {effectiveViewMode === "single" && periods.length > 0 && (
          <>
            <span className="mx-1 text-gray-300">|</span>
            <select
              value={periodIndex}
              onChange={(e) => setPeriodIndex(Number(e.target.value))}
              className="rounded-lg border border-indigo-100 bg-white px-2 py-1 text-xs text-indigo-800 focus:border-indigo-300 focus:outline-none"
            >
              {periods.map((p, i) => (
                <option key={p.period_end ?? `${p.fiscal_year}-${p.fiscal_period}`} value={i}>
                  {periodHeader(p)}
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
        ) : effectiveViewMode === "compare" ? (
          <ComparisonTable
            headers={periodHeaders}
            labels={comparison.labels}
            cells={comparison.cells}
            rowItems={comparison.items}
            rowKeys={comparison.keys}
            periods={periods}
            coverage={financials.coverage ?? undefined}
            periodType={periodType}
          />
        ) : activePeriod ? (
          <SinglePeriodTable
            period={activePeriod}
            statement={statement}
            coverage={financials.coverage ?? undefined}
          />
        ) : (
          <p className="text-sm text-gray-400">No line items for this period.</p>
        )}
      </div>
    </div>
  );
}

function coverageHint(
  key: string,
  item: LineItem | undefined,
  coverage?: Record<string, CoverageEntry>,
): string | undefined {
  const derived = sourceHint(item);
  if (derived) return derived;
  const cov = coverage?.[key];
  if (!item && cov?.reason) return cov.reason;
  if (cov?.status === "not_applicable") return cov.reason ?? "Not applicable for this filer";
  return undefined;
}

function CellValue({
  display,
  hint,
  missing,
}: {
  display: string;
  hint?: string;
  missing?: boolean;
}) {
  if (display !== "—") {
    return (
      <span title={hint} className="tabular-nums">
        {display}
      </span>
    );
  }
  return (
    <span
      title={hint ?? "Not in SEC filing for this period"}
      className={`tabular-nums ${missing ? "text-gray-300" : "text-amber-500/80"}`}
    >
      {missing ? "N/A" : "—"}
    </span>
  );
}
function sourceHint(item: LineItem | undefined): string | undefined {
  if (!item || item.source !== "derived") return undefined;
  const parts = item.derived_from?.join(" + ") ?? "components";
  return `Calculated from SEC line items: ${parts}`;
}

function LineItemLabel({
  label,
  item,
  coverageKey,
  coverage,
}: {
  label: string;
  item?: LineItem;
  coverageKey?: string;
  coverage?: Record<string, CoverageEntry>;
}) {
  const hint =
    sourceHint(item) ??
    (coverageKey ? coverageHint(coverageKey, item, coverage) : undefined);
  return (
    <span className="inline-flex items-center gap-1">
      {label}
      {hint && item?.source === "derived" && (
        <span
          className="cursor-help rounded px-0.5 text-[10px] font-normal text-violet-500"
          title={hint}
        >
          †
        </span>
      )}
    </span>
  );
}

function ComparisonTable({
  headers,
  labels,
  cells,
  rowItems,
  rowKeys,
  periods,
  coverage,
  periodType,
}: {
  headers: string[];
  labels: string[];
  cells: string[][];
  rowItems: (LineItem | undefined)[][];
  rowKeys: string[];
  periods: StatementPeriod[];
  coverage?: Record<string, CoverageEntry>;
  periodType: PeriodType;
}) {
  return (
    <>
      <div className="overflow-x-auto">
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
          {labels.map((label, ri) => {
            const key = rowKeys[ri];
            const cov = coverage?.[key];
            const isNa = cov?.status === "not_applicable";
            return (
              <tr
                key={label}
                className="border-b border-gray-50 hover:bg-indigo-50/30"
              >
                <td className="sticky left-0 z-10 bg-white py-2 pr-4 text-gray-700">
                  <LineItemLabel
                    label={label}
                    item={rowItems[ri]?.[0]}
                    coverageKey={key}
                    coverage={coverage}
                  />
                </td>
                {cells[ri].map((cell, ci) => (
                  <td key={ci} className="px-2 py-2 text-right font-medium text-gray-900">
                    <CellValue
                      display={cell}
                      hint={coverageHint(key, rowItems[ri]?.[ci], coverage)}
                      missing={isNa}
                    />
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
      </div>
      {periods[0]?.filed && (
        <p className="mt-4 text-xs text-gray-400">
          {periodType === "annual" ? "Annual" : "Quarterly"} comparison · {periods.length}{" "}
          {periodType === "annual" ? "years" : "quarters"} · SEC XBRL
          <span className="text-violet-400"> · † calculated from filed components</span>
        </p>
      )}
      {!periods[0]?.filed && periods.length > 0 && (
        <p className="mt-4 text-xs text-gray-400">
          {periodType === "annual" ? "Annual" : "Quarterly"} comparison · {periods.length}{" "}
          {periodType === "annual" ? "years" : "quarters"} · SEC XBRL
          <span className="text-violet-400"> · † calculated from filed components</span>
        </p>
      )}
    </>
  );
}

function SinglePeriodTable({
  period,
  statement,
  coverage,
}: {
  period: StatementPeriod;
  statement: StatementKey;
  coverage?: Record<string, CoverageEntry>;
}) {
  const order = STATEMENT_METRIC_ORDER[statement] ?? [];
  const itemMap = Object.fromEntries(period.line_items.map((li) => [li.key, li]));
  const keys = [
    ...order,
    ...period.line_items.map((li) => li.key).filter((k) => !order.includes(k)),
  ];

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
          {keys.map((key) => {
            const item = itemMap[key];
            const label = item?.label ?? METRIC_LABELS[key] ?? key;
            const cov = coverage?.[key];
            const isNa = cov?.status === "not_applicable";
            return (
              <tr key={key} className="border-b border-gray-50 hover:bg-indigo-50/30">
                <td className="py-2 pr-4 text-gray-700">
                  <LineItemLabel
                    label={label}
                    item={item}
                    coverageKey={key}
                    coverage={coverage}
                  />
                </td>
                <td className="py-2 text-right font-medium text-gray-900">
                  {item ? (
                    <span title={sourceHint(item)} className="tabular-nums">
                      {fmtDisplay(item.value, item.unit)}
                    </span>
                  ) : (
                    <CellValue
                      display="—"
                      hint={coverageHint(key, undefined, coverage)}
                      missing={isNa}
                    />
                  )}
                </td>
              </tr>
            );
          })}
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
