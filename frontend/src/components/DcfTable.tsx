import type { DcfResult } from "../types";

function fmtM(value: number): string {
  const abs = Math.abs(value).toLocaleString(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  });
  return value < 0 ? `($${abs}M)` : `$${abs}M`;
}

function fmtPct(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function fmtRateDisplay(value: number | number[]): string {
  if (Array.isArray(value)) {
    const pcts = value.map((v) => (Math.abs(v) <= 1 ? v * 100 : v));
    const unique = [...new Set(pcts.map((v) => v.toFixed(1)))];
    return unique.length === 1 ? `${unique[0]}%` : "per year";
  }
  return fmtPct(value);
}

function fmtMult(value: number): string {
  return value.toFixed(3);
}

interface DcfTableProps {
  model: DcfResult;
}

interface YearMetrics {
  revenue: number;
  growth: number;
  ebitda: number;
  da: number;
  ebit: number;
  taxes: number;
  capex: number;
  nwc: number;
  deltaNwc: number;
  ufcf: number;
  terminalValue: number;
  totalUfcf: number;
  discountFactor: number;
  pvUfcf: number;
}

export default function DcfTable({ model }: DcfTableProps) {
  const { inputs, years } = model;
  const pvExplicit = years.reduce((sum, y) => sum + y.pv_fcf, 0);
  const tvPct =
    model.enterprise_value > 0
      ? (model.pv_terminal / model.enterprise_value) * 100
      : 0;
  const tvPctWarning = tvPct > 85;

  const metrics: YearMetrics[] = years.map((row, i) => {
    const prevRevenue = i === 0 ? inputs.base_revenue : years[i - 1].revenue;
    return {
      revenue: row.revenue,
      growth: row.revenue / prevRevenue - 1,
      ebitda: row.ebitda,
      da: row.da,
      ebit: row.ebit,
      taxes: row.taxes,
      capex: row.capex,
      nwc: row.nwc,
      deltaNwc: row.delta_nwc,
      ufcf: row.ufcf,
      terminalValue: row.terminal_value,
      totalUfcf: row.total_ufcf,
      discountFactor: row.discount_factor,
      pvUfcf: row.pv_fcf,
    };
  });

  const yearLabels = years.map((y) => `Year ${y.year}`);

  return (
    <div className="flex h-full flex-col overflow-hidden bg-white text-sm">
      <div className="shrink-0 border-b border-gray-300 bg-slate-50 px-4 py-3">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Valuation Summary
        </h3>
        <div className="grid gap-x-8 gap-y-1 sm:grid-cols-2">
          <BridgeLine label="PV of Explicit Period" value={fmtM(pvExplicit)} />
          <BridgeLine
            label="PV of Terminal Value"
            value={fmtM(model.pv_terminal)}
            sub={
              tvPctWarning
                ? `TV is ${tvPct.toFixed(1)}% of EV — above typical 60–80% range`
                : `TV is ${tvPct.toFixed(1)}% of total EV`
            }
            warn={tvPctWarning}
          />
          <BridgeLine
            label="Implied Enterprise Value"
            value={fmtM(model.enterprise_value)}
            bold
          />
          {inputs.net_debt != null && (
            <BridgeLine label="Less: Net Debt" value={fmtM(inputs.net_debt)} />
          )}
          {model.equity_value != null && (
            <BridgeLine
              label="Implied Equity Value"
              value={fmtM(model.equity_value)}
              bold
            />
          )}
          {model.price_per_share != null && (
            <BridgeLine
              label="Implied Share Price"
              value={`$${model.price_per_share.toFixed(2)}`}
              bold
            />
          )}
        </div>
      </div>

      <div className="shrink-0 border-b border-gray-200 px-4 py-2">
        <h3 className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Key Assumptions
        </h3>
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-gray-600">
          <span>WACC {fmtPct(inputs.wacc)}</span>
          <span>Terminal g {fmtPct(inputs.terminal_growth)}</span>
          <span>Tax {fmtRateDisplay(inputs.tax_rate)}</span>
          <span>EBITDA margin {fmtRateDisplay(inputs.ebitda_margin)}</span>
          <span>D&A {fmtRateDisplay(inputs.da_pct)} of rev</span>
          <span>CapEx {fmtRateDisplay(inputs.capex_pct)} of rev</span>
          <span>NWC {fmtRateDisplay(inputs.nwc_pct)} of rev</span>
          <span>{inputs.projection_years}-year explicit forecast</span>
          <span>Units: $M USD</span>
        </div>
      </div>

      <div className="flex-1 overflow-auto p-4">
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-gray-500">
          Unlevered Free Cash Flow ($M)
        </h3>
        <table className="w-full min-w-[560px] border-collapse text-xs">
          <thead>
            <tr className="border-b-2 border-gray-800">
              <th className="sticky left-0 z-10 bg-white py-2 pr-4 text-left font-semibold text-gray-700">
                &nbsp;
              </th>
              {yearLabels.map((label) => (
                <th
                  key={label}
                  className="px-2 py-2 text-right font-semibold text-gray-800"
                >
                  {label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <SectionHeader label="Operating" colSpan={yearLabels.length} />
            <DataRow label="Revenue" values={metrics.map((m) => fmtM(m.revenue))} bold />
            <DataRow
              label="  % Growth"
              values={metrics.map((m) => fmtPct(m.growth))}
              muted
            />
            <DataRow label="EBITDA" values={metrics.map((m) => fmtM(m.ebitda))} bold />
            <DataRow
              label="  EBITDA Margin"
              values={metrics.map((m) => fmtPct(m.ebitda / m.revenue))}
              muted
            />
            <DataRow label="Less: D&A" values={metrics.map((m) => fmtM(-m.da))} />
            <DataRow label="EBIT" values={metrics.map((m) => fmtM(m.ebit))} bold />

            <SectionHeader label="UFCF Build" colSpan={yearLabels.length} />
            <DataRow label="Less: Taxes (on EBIT)" values={metrics.map((m) => fmtM(-m.taxes))} />
            <DataRow label="Less: CapEx" values={metrics.map((m) => fmtM(-m.capex))} />
            <DataRow label="Net Working Capital" values={metrics.map((m) => fmtM(m.nwc))} muted />
            <DataRow
              label="Less: Δ Net Working Capital"
              values={metrics.map((m) => fmtM(-m.deltaNwc))}
            />
            <DataRow
              label="Unlevered Free Cash Flow"
              values={metrics.map((m) => fmtM(m.ufcf))}
              bold
              total
            />
            <DataRow
              label="Terminal Value"
              values={metrics.map((m) => fmtM(m.terminalValue))}
            />
            <DataRow
              label="Total UFCF"
              values={metrics.map((m) => fmtM(m.totalUfcf))}
              bold
              total
            />

            <SectionHeader label="Discounting" colSpan={yearLabels.length} />
            <DataRow
              label="Discount Factor"
              values={metrics.map((m) => fmtMult(m.discountFactor))}
              muted
            />
            <DataRow
              label="PV of Total UFCF"
              values={metrics.map((m) => fmtM(m.pvUfcf))}
              bold
              total
            />
          </tbody>
        </table>

        <table className="mt-4 w-full max-w-md border-collapse text-xs">
          <tbody>
            <SectionHeader label="Terminal Value (Gordon Growth)" colSpan={2} />
            <tr className="border-b border-gray-100">
              <td className="py-1.5 pr-4 text-gray-700">
                Terminal Value (undiscounted)
              </td>
              <td className="py-1.5 text-right font-medium tabular-nums">
                {fmtM(model.terminal_value)}
              </td>
            </tr>
            <tr className="border-b border-gray-200">
              <td className="py-1.5 pr-4 text-gray-700">PV of Terminal Value</td>
              <td className="py-1.5 text-right font-semibold tabular-nums">
                {fmtM(model.pv_terminal)}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

function BridgeLine({
  label,
  value,
  bold = false,
  sub,
  warn = false,
}: {
  label: string;
  value: string;
  bold?: boolean;
  sub?: string;
  warn?: boolean;
}) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <div>
        <span className={bold ? "font-semibold text-gray-900" : "text-gray-600"}>
          {label}
        </span>
        {sub && (
          <p className={`text-xs ${warn ? "text-amber-600" : "text-gray-400"}`}>
            {sub}
          </p>
        )}
      </div>
      <span
        className={`shrink-0 tabular-nums ${bold ? "text-base font-bold text-gray-900" : "font-medium text-gray-800"}`}
      >
        {value}
      </span>
    </div>
  );
}

function SectionHeader({ label, colSpan }: { label: string; colSpan: number }) {
  return (
    <tr>
      <td
        colSpan={colSpan + 1}
        className="bg-gray-100 px-0 py-1.5 text-[10px] font-semibold uppercase tracking-wide text-gray-500"
      >
        {label}
      </td>
    </tr>
  );
}

function DataRow({
  label,
  values,
  bold = false,
  muted = false,
  total = false,
}: {
  label: string;
  values: string[];
  bold?: boolean;
  muted?: boolean;
  total?: boolean;
}) {
  return (
    <tr className={total ? "border-t border-gray-800" : "border-b border-gray-100"}>
      <td
        className={`sticky left-0 z-10 bg-white py-1.5 pr-4 ${
          bold ? "font-semibold text-gray-900" : muted ? "text-gray-500" : "text-gray-700"
        }`}
      >
        {label}
      </td>
      {values.map((v, i) => (
        <td
          key={i}
          className={`px-2 py-1.5 text-right tabular-nums ${
            bold ? "font-semibold text-gray-900" : muted ? "text-gray-500" : "text-gray-800"
          }`}
        >
          {v}
        </td>
      ))}
    </tr>
  );
}
