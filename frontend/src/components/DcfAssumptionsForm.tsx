import type { ReactNode } from "react";
import type { DcfDraftDefaults, DcfDraftInputs } from "../types";
import NumberInput from "./NumberInput";
import PercentInput from "./PercentInput";

interface DcfAssumptionsFormProps {
  inputs: DcfDraftInputs;
  defaults: DcfDraftDefaults;
  onChange: (patch: Partial<DcfDraftInputs>) => void;
  onDefaultsChange: (patch: DcfDraftDefaults) => void;
  onFillForecastRows: () => void;
}

const pctInputClass =
  "w-full rounded-lg border border-indigo-200 bg-blue-50/50 px-2.5 py-1.5 text-sm tabular-nums text-gray-900 focus:border-indigo-400 focus:outline-none focus:ring-1 focus:ring-indigo-300";

function Field({
  label,
  optional,
  children,
}: {
  label: string;
  optional?: boolean;
  children: ReactNode;
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium text-gray-600">
        {label}
        {optional && (
          <span className="ml-1 font-normal text-gray-400">(Optional)</span>
        )}
      </span>
      {children}
    </label>
  );
}

export default function DcfAssumptionsForm({
  inputs,
  defaults,
  onChange,
  onDefaultsChange,
  onFillForecastRows,
}: DcfAssumptionsFormProps) {
  const hasForecastDefaults = [
    defaults.revenue_growth,
    defaults.ebitda_margin,
    defaults.da_pct,
    defaults.tax_rate,
    defaults.capex_pct,
    defaults.nwc_pct,
  ].some((v) => v != null);

  return (
    <section className="space-y-4 rounded-xl border border-gray-200 bg-white p-4">
      <h3 className="text-sm font-semibold text-gray-800">Global assumptions ($M USD)</h3>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="WACC">
          <div className="relative">
            <PercentInput
              value={inputs.wacc}
              onChange={(v) => onChange({ wacc: v })}
              className={pctInputClass}
            />
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
              %
            </span>
          </div>
        </Field>
        <Field label="Terminal growth">
          <div className="relative">
            <PercentInput
              value={inputs.terminal_growth}
              onChange={(v) => onChange({ terminal_growth: v })}
              className={pctInputClass}
            />
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
              %
            </span>
          </div>
        </Field>
        <Field label="Base revenue">
          <div className="relative">
            <NumberInput
              value={inputs.base_revenue}
              onChange={(v) => onChange({ base_revenue: v })}
              className={pctInputClass}
            />
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
              $M
            </span>
          </div>
        </Field>
        <Field label="Net debt" optional>
          <div className="relative">
            <NumberInput
              value={inputs.net_debt}
              onChange={(v) => onChange({ net_debt: v })}
              className={pctInputClass}
            />
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
              $M
            </span>
          </div>
        </Field>
        <Field label="Shares outstanding" optional>
          <div className="relative">
            <NumberInput
              value={inputs.shares_outstanding}
              onChange={(v) => onChange({ shares_outstanding: v })}
              className={pctInputClass}
            />
            <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
              M sh
            </span>
          </div>
        </Field>
      </div>

      <div>
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div>
            <h4 className="text-xs font-medium text-gray-500">Forecast defaults</h4>
            <p className="text-[11px] text-gray-400">Fill all years or type year-by-year below</p>
          </div>
          <button
            type="button"
            onClick={onFillForecastRows}
            disabled={!hasForecastDefaults}
            className="rounded-lg border border-indigo-300 bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-800 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:opacity-40"
          >
            Fill all years
          </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-6">
          {(
            [
              ["Revenue growth", "revenue_growth"],
              ["EBITDA margin", "ebitda_margin"],
              ["D&A % rev", "da_pct"],
              ["Tax rate", "tax_rate"],
              ["CapEx % rev", "capex_pct"],
              ["NWC % rev", "nwc_pct"],
            ] as const
          ).map(([label, key]) => (
            <Field key={key} label={label}>
              <div className="relative">
                <PercentInput
                  value={defaults[key]}
                  onChange={(v) => onDefaultsChange({ ...defaults, [key]: v })}
                  className={pctInputClass}
                />
                <span className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-xs text-gray-400">
                  %
                </span>
              </div>
            </Field>
          ))}
        </div>
      </div>
    </section>
  );
}
