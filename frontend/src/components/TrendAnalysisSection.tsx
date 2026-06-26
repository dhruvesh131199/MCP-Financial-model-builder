import type { TrendAnalysisData } from "../types";

function fmtUsd(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1e9) return `$${(value / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(value / 1e6).toFixed(1)}M`;
  return `$${value.toLocaleString()}`;
}

function fmtCell(rowType: TrendAnalysisData["rows"][0]["row_type"], value: number | null): string {
  if (value == null) return "—";
  if (rowType === "currency") return fmtUsd(value);
  if (rowType === "eps") return `$${value.toFixed(2)}`;
  return `${value.toFixed(1)}%`;
}

interface TrendAnalysisSectionProps {
  trend: TrendAnalysisData;
}

export default function TrendAnalysisSection({ trend }: TrendAnalysisSectionProps) {
  return (
    <section className="mb-10">
      <h3 className="mb-3 border-b border-gray-200 pb-2 text-sm font-semibold text-gray-900">
        Trend analysis
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[32rem] border-collapse text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-gray-500">
              <th className="py-2 pr-3 text-left font-medium">Line item</th>
              {trend.fiscal_years.map((fy) => (
                <th
                  key={fy}
                  className="px-2 py-2 text-right font-medium tabular-nums"
                >
                  FY{fy}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trend.rows.map((row) => (
              <tr
                key={row.key}
                className={`border-b border-gray-100 ${
                  row.highlight ? "bg-slate-50 font-semibold" : "hover:bg-gray-50/80"
                }`}
              >
                <td className="py-2 pr-3 font-medium text-gray-800">{row.label}</td>
                {row.values.map((value, i) => (
                  <td
                    key={`${row.key}-${i}`}
                    className={`px-2 py-2 text-right tabular-nums ${
                      value == null ? "text-gray-300" : "text-gray-900"
                    }`}
                  >
                    {fmtCell(row.row_type, value)}
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
