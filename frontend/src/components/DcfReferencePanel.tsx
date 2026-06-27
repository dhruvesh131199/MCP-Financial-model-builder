import type { DcfReferenceHistory } from "../types";

function fmtRefValue(value: number | null, format: string): string {
  if (value == null || Number.isNaN(value)) return "—";
  if (format === "currency_m") {
    return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}M`;
  }
  if (format === "currency") {
    const m = value / 1_000_000;
    return `$${m.toLocaleString(undefined, { maximumFractionDigits: 0 })}M`;
  }
  if (format === "percent") {
    const pct = Math.abs(value) <= 1 ? value * 100 : value;
    return `${pct.toFixed(1)}%`;
  }
  if (format === "ratio") {
    return value.toFixed(2);
  }
  return String(value);
}

interface DcfReferencePanelProps {
  reference: DcfReferenceHistory;
}

export default function DcfReferencePanel({ reference }: DcfReferencePanelProps) {
  const { fiscal_years, rows, latest_revenue_usd, ticker, hints, units_note } = reference;

  return (
    <section className="rounded-xl border border-indigo-200/80 bg-gradient-to-br from-slate-50 to-indigo-50/40 p-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-indigo-900">
            SEC reference — 5 fiscal years
          </h3>
          <p className="text-xs text-gray-500">
            Historical reference only ({ticker}). {units_note ?? "All amounts in $M USD."}
          </p>
          <p className="mt-1 text-[11px] text-gray-400">
            EBITDA margin uses tagged EBITDA or operating income + D&amp;A when complete in
            filings. Blank when SEC lacks a reliable add-back — use operating margin or enter
            your own forecast margin.
          </p>
        </div>
        {latest_revenue_usd != null && (
          <p className="text-xs text-gray-600">
            Latest FY revenue:{" "}
            <span className="font-medium text-indigo-900">
              {fmtRefValue(latest_revenue_usd, "currency")}
            </span>
          </p>
        )}
      </div>

      {hints?.shares_outstanding_m != null && (
        <p className="mb-2 text-xs text-indigo-800/80">
          Shares hint ({hints.shares_source ?? "unknown"}):{" "}
          <span className="font-medium">{hints.shares_outstanding_m.toLocaleString()}M</span>
          {" — copied to optional field below when draft is created."}
        </p>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full border-collapse text-xs">
          <thead>
            <tr className="border-b border-indigo-100">
              <th className="py-2 pr-4 text-left font-medium text-gray-500">Metric</th>
              {fiscal_years.map((fy) => (
                <th
                  key={fy}
                  className="px-3 py-2 text-right font-medium text-indigo-800"
                >
                  FY{fy}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} className="border-b border-indigo-50/80">
                <td className="py-1.5 pr-4 text-gray-700">{row.label}</td>
                {row.values.map((val, i) => (
                  <td
                    key={`${row.key}-${fiscal_years[i]}`}
                    className="px-3 py-1.5 text-right tabular-nums text-gray-800"
                  >
                    {fmtRefValue(val, row.format)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
