import type { DcfDraftInputs } from "../types";
import type { DcfPreview } from "../lib/dcfCompute";
import PercentInput from "./PercentInput";

type EditableKey =
  | "revenue_growth"
  | "ebitda_margin"
  | "da_pct"
  | "tax_rate"
  | "capex_pct"
  | "nwc_pct";

interface DcfForecastGridProps {
  projectionYears: number;
  inputs: DcfDraftInputs;
  preview: DcfPreview | null;
  onChange: (patch: Partial<DcfDraftInputs>) => void;
}

const EDITABLE_ROWS: { key: EditableKey; label: string }[] = [
  { key: "revenue_growth", label: "Revenue growth %" },
  { key: "ebitda_margin", label: "EBITDA margin %" },
  { key: "da_pct", label: "D&A % rev" },
  { key: "tax_rate", label: "Tax %" },
  { key: "capex_pct", label: "CapEx % rev" },
  { key: "nwc_pct", label: "NWC % rev" },
];

const cellClass =
  "w-full rounded border border-indigo-200 bg-blue-50/60 px-1.5 py-1 text-right tabular-nums focus:border-indigo-400 focus:outline-none";

function fmtM(v: number): string {
  return `$${v.toLocaleString(undefined, { maximumFractionDigits: 1 })}M`;
}

export default function DcfForecastGrid({
  projectionYears,
  inputs,
  preview,
  onChange,
}: DcfForecastGridProps) {
  const yearLabels = Array.from({ length: projectionYears }, (_, i) => `Year ${i + 1}`);

  function updateCell(key: EditableKey, index: number, decimal: number | null) {
    const arr = [...inputs[key]];
    arr[index] = decimal;
    onChange({ [key]: arr });
  }

  return (
    <section className="overflow-x-auto rounded-xl border border-gray-200 bg-white p-4">
      <h3 className="mb-3 text-sm font-semibold text-gray-800">
        {projectionYears}-year forecast ($M USD)
      </h3>
      <table className="min-w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-gray-200 bg-slate-50">
            <th className="sticky left-0 z-10 bg-slate-50 py-2 pr-4 text-left font-medium text-gray-500">
              (% inputs · $M computed)
            </th>
            {yearLabels.map((label) => (
              <th
                key={label}
                className="min-w-[88px] px-2 py-2 text-right font-medium text-gray-700"
              >
                {label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {EDITABLE_ROWS.map(({ key, label }) => (
            <tr key={key} className="border-b border-gray-100">
              <td className="sticky left-0 z-10 bg-white py-1 pr-4 text-gray-700">{label}</td>
              {Array.from({ length: projectionYears }).map((_, i) => (
                <td key={`${key}-${i}`} className="px-1 py-0.5">
                  <PercentInput
                    value={inputs[key][i]}
                    onChange={(v) => updateCell(key, i, v)}
                    className={cellClass}
                  />
                </td>
              ))}
            </tr>
          ))}

          {preview && (
            <>
              <ComputedRow label="Revenue" values={preview.years.map((y) => fmtM(y.revenue))} />
              <ComputedRow label="EBITDA" values={preview.years.map((y) => fmtM(y.ebitda))} />
              <ComputedRow label="D&A" values={preview.years.map((y) => fmtM(y.da))} />
              <ComputedRow label="EBIT" values={preview.years.map((y) => fmtM(y.ebit))} />
              <ComputedRow label="Taxes (on EBIT)" values={preview.years.map((y) => fmtM(y.taxes))} />
              <ComputedRow label="CapEx" values={preview.years.map((y) => fmtM(y.capex))} />
              <ComputedRow label="NWC" values={preview.years.map((y) => fmtM(y.nwc))} />
              <ComputedRow
                label="ΔNWC"
                values={preview.years.map((y) => fmtM(y.deltaNwc))}
              />
              <ComputedRow label="UFCF" values={preview.years.map((y) => fmtM(y.ufcf))} bold />
              <ComputedRow
                label="Terminal Value"
                values={preview.years.map((y) => fmtM(y.terminalValue))}
              />
              <ComputedRow
                label="Total UFCF"
                values={preview.years.map((y) => fmtM(y.totalUfcf))}
                bold
              />
              <ComputedRow
                label="Discount factor"
                values={preview.years.map((y) => y.discountFactor.toFixed(3))}
              />
              <ComputedRow
                label="PV of Total UFCF"
                values={preview.years.map((y) => fmtM(y.pvUfcf))}
                bold
              />
            </>
          )}
        </tbody>
      </table>

      {preview && (
        <div className="mt-4 grid gap-2 border-t border-gray-100 pt-4 sm:grid-cols-2 lg:grid-cols-4">
          <SummaryChip label="Enterprise value" value={fmtM(preview.enterpriseValue)} />
          <SummaryChip label="PV terminal" value={fmtM(preview.pvTerminal)} />
          {preview.equityValue != null && (
            <SummaryChip label="Equity value" value={fmtM(preview.equityValue)} />
          )}
          {preview.pricePerShare != null && (
            <SummaryChip
              label="Price / share"
              value={`$${preview.pricePerShare.toFixed(2)}`}
            />
          )}
        </div>
      )}
    </section>
  );
}

function ComputedRow({
  label,
  values,
  bold,
}: {
  label: string;
  values: string[];
  bold?: boolean;
}) {
  return (
    <tr className="border-b border-gray-50 bg-gray-50/80">
      <td
        className={`sticky left-0 z-10 bg-gray-50/95 py-1.5 pr-4 text-gray-600 ${bold ? "font-semibold" : ""}`}
      >
        {label}
      </td>
      {values.map((v, i) => (
        <td
          key={`${label}-${i}`}
          className={`px-2 py-1.5 text-right tabular-nums text-gray-700 ${bold ? "font-semibold" : ""}`}
        >
          {v}
        </td>
      ))}
    </tr>
  );
}

function SummaryChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-indigo-50/80 px-3 py-2">
      <p className="text-[10px] uppercase tracking-wide text-indigo-600">{label}</p>
      <p className="text-sm font-semibold text-indigo-950">{value}</p>
    </div>
  );
}
