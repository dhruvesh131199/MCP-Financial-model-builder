import type { DcfDraftDefaults, DcfDraftInputs, DcfResult } from "../types";

export function normalizeRate(value: number): number {
  return Math.abs(value) > 1 ? value / 100 : value;
}

export function rateSeries(
  value: number | number[] | (number | null)[] | null | undefined,
  years: number,
  fallback = 0,
): number[] {
  if (value == null) return Array(years).fill(fallback);
  if (Array.isArray(value)) {
    return value.map((v) => (v == null ? fallback : normalizeRate(v)));
  }
  const r = normalizeRate(value);
  return Array(years).fill(r);
}

export interface PreviewYearRow {
  year: number;
  revenue: number;
  ebitda: number;
  taxes: number;
  nopat: number;
  capex: number;
  deltaNwc: number;
  ufcf: number;
  discountFactor: number;
  pvUfcf: number;
}

export interface DcfPreview {
  years: PreviewYearRow[];
  terminalValue: number;
  pvTerminal: number;
  enterpriseValue: number;
  equityValue: number | null;
  pricePerShare: number | null;
}

export function computeDcfPreview(
  inputs: DcfDraftInputs,
  projectionYears: number,
): DcfPreview | null {
  if (
    inputs.base_revenue == null ||
    inputs.wacc == null ||
    inputs.terminal_growth == null
  ) {
    return null;
  }

  const wacc = normalizeRate(inputs.wacc);
  const g = normalizeRate(inputs.terminal_growth);
  if (wacc <= g) return null;

  const growths = rateSeries(inputs.revenue_growth, projectionYears);
  const margins = rateSeries(inputs.ebitda_margin, projectionYears);
  const taxes = rateSeries(inputs.tax_rate, projectionYears);
  const capexPcts = rateSeries(inputs.capex_pct, projectionYears);
  const nwcPcts = rateSeries(inputs.nwc_pct, projectionYears);

  if (
    inputs.revenue_growth.some((v) => v == null) ||
    inputs.ebitda_margin.some((v) => v == null) ||
    inputs.tax_rate.some((v) => v == null) ||
    inputs.capex_pct.some((v) => v == null) ||
    inputs.nwc_pct.some((v) => v == null)
  ) {
    return null;
  }

  let revenue = inputs.base_revenue;
  const years: PreviewYearRow[] = [];
  let pvSum = 0;
  let finalUfcf = 0;

  for (let t = 1; t <= projectionYears; t++) {
    const idx = t - 1;
    revenue = revenue * (1 + growths[idx]);
    const prevRevenue = revenue / (1 + growths[idx]);
    const ebitda = revenue * margins[idx];
    const taxAmt = ebitda * taxes[idx];
    const nopat = ebitda - taxAmt;
    const capex = revenue * capexPcts[idx];
    const deltaNwc = (revenue - prevRevenue) * nwcPcts[idx];
    const ufcf = nopat - capex - deltaNwc;
    const discountFactor = 1 / (1 + wacc) ** t;
    const pvUfcf = ufcf * discountFactor;
    pvSum += pvUfcf;
    finalUfcf = ufcf;

    years.push({
      year: t,
      revenue,
      ebitda,
      taxes: taxAmt,
      nopat,
      capex,
      deltaNwc,
      ufcf,
      discountFactor,
      pvUfcf,
    });
  }

  const terminalValue = (finalUfcf * (1 + g)) / (wacc - g);
  const pvTerminal = terminalValue / (1 + wacc) ** projectionYears;
  const enterpriseValue = pvSum + pvTerminal;

  let equityValue: number | null = null;
  let pricePerShare: number | null = null;
  if (inputs.net_debt != null) {
    equityValue = enterpriseValue - inputs.net_debt;
    if (inputs.shares_outstanding != null && inputs.shares_outstanding > 0) {
      pricePerShare = equityValue / inputs.shares_outstanding;
    }
  }

  return {
    years,
    terminalValue,
    pvTerminal,
    enterpriseValue,
    equityValue,
    pricePerShare,
  };
}

export function draftInputsReady(
  inputs: DcfDraftInputs,
  projectionYears: number,
): boolean {
  if (
    inputs.base_revenue == null ||
    inputs.wacc == null ||
    inputs.terminal_growth == null
  ) {
    return false;
  }
  const arrays = [
    inputs.revenue_growth,
    inputs.ebitda_margin,
    inputs.tax_rate,
    inputs.capex_pct,
    inputs.nwc_pct,
  ];
  return arrays.every(
    (arr) =>
      arr.length === projectionYears && arr.every((v) => v != null && !Number.isNaN(v)),
  );
}

export function applyDefaultToRow(
  inputs: DcfDraftInputs,
  key: keyof Pick<
    DcfDraftInputs,
    "revenue_growth" | "ebitda_margin" | "tax_rate" | "capex_pct" | "nwc_pct"
  >,
  value: number,
  projectionYears: number,
): DcfDraftInputs {
  const normalized = normalizeRate(value);
  return {
    ...inputs,
    [key]: Array(projectionYears).fill(normalized),
  };
}

export function applyAllDefaults(
  inputs: DcfDraftInputs,
  defaults: DcfDraftDefaults,
  projectionYears: number,
): DcfDraftInputs {
  let next = { ...inputs };
  const rows: {
    key: keyof Pick<
      DcfDraftInputs,
      "revenue_growth" | "ebitda_margin" | "tax_rate" | "capex_pct" | "nwc_pct"
    >;
    val: number | null | undefined;
  }[] = [
    { key: "revenue_growth", val: defaults.revenue_growth },
    { key: "ebitda_margin", val: defaults.ebitda_margin },
    { key: "tax_rate", val: defaults.tax_rate },
    { key: "capex_pct", val: defaults.capex_pct },
    { key: "nwc_pct", val: defaults.nwc_pct },
  ];
  for (const { key, val } of rows) {
    if (val != null) {
      next = applyDefaultToRow(next, key, val, projectionYears);
    }
  }
  return next;
}

export function resultFromPreview(
  preview: DcfPreview,
  inputs: DcfDraftInputs,
  projectionYears: number,
  companyName?: string | null,
): DcfResult {
  return {
    company_name: companyName,
    inputs: {
      base_revenue: inputs.base_revenue!,
      revenue_growth: inputs.revenue_growth.map((v) => v!),
      ebitda_margin: inputs.ebitda_margin.map((v) => v!),
      tax_rate: inputs.tax_rate.map((v) => v!),
      capex_pct: inputs.capex_pct.map((v) => v!),
      nwc_pct: inputs.nwc_pct.map((v) => v!),
      wacc: inputs.wacc!,
      terminal_growth: inputs.terminal_growth!,
      projection_years: projectionYears,
      net_debt: inputs.net_debt,
      shares_outstanding: inputs.shares_outstanding,
    },
    years: preview.years.map((y) => ({
      year: y.year,
      revenue: y.revenue,
      ebitda: y.ebitda,
      fcf: y.ufcf,
      pv_fcf: y.pvUfcf,
    })),
    terminal_value: preview.terminalValue,
    pv_terminal: preview.pvTerminal,
    enterprise_value: preview.enterpriseValue,
    equity_value: preview.equityValue,
    price_per_share: preview.pricePerShare,
  };
}

export type { DcfDraftDefaults };
