import { describe, expect, it } from "vitest";
import {
  applyAllDefaults,
  computeDcfPreview,
  draftInputsReady,
  normalizeRate,
} from "./dcfCompute";
import type { DcfDraftInputs } from "../types";

describe("dcfCompute", () => {
  it("normalizes percent inputs", () => {
    expect(normalizeRate(10)).toBe(0.1);
    expect(normalizeRate(0.1)).toBe(0.1);
  });

  it("preview returns null until required fields filled", () => {
    const inputs: DcfDraftInputs = {
      base_revenue: null,
      wacc: null,
      terminal_growth: null,
      revenue_growth: [null, null, null],
      ebitda_margin: [null, null, null],
      da_pct: [null, null, null],
      tax_rate: [null, null, null],
      capex_pct: [null, null, null],
      nwc_pct: [null, null, null],
    };
    expect(computeDcfPreview(inputs, 3)).toBeNull();
    expect(draftInputsReady(inputs, 3)).toBe(false);
  });

  it("preview computes EV for filled 3-year draft", () => {
    const inputs: DcfDraftInputs = {
      base_revenue: 1000,
      wacc: 0.1,
      terminal_growth: 0.02,
      revenue_growth: [0.05, 0.05, 0.05],
      ebitda_margin: [0.3, 0.3, 0.3],
      da_pct: [0.04, 0.04, 0.04],
      tax_rate: [0.21, 0.21, 0.21],
      capex_pct: [0.04, 0.04, 0.04],
      nwc_pct: [0.02, 0.02, 0.02],
    };
    const preview = computeDcfPreview(inputs, 3);
    expect(preview).not.toBeNull();
    expect(preview!.years).toHaveLength(3);
    expect(preview!.enterpriseValue).toBeGreaterThan(0);
    expect(draftInputsReady(inputs, 3)).toBe(true);
  });

  it("handles negative rate inputs (declining revenue, net cash)", () => {
    const inputs: DcfDraftInputs = {
      base_revenue: 1000,
      wacc: 0.1,
      terminal_growth: 0.02,
      revenue_growth: [-0.05, -0.05],
      ebitda_margin: [0.3, 0.3],
      da_pct: [0.04, 0.04],
      tax_rate: [0.21, 0.21],
      capex_pct: [0.04, 0.04],
      nwc_pct: [0.02, 0.02],
      net_debt: -200,
    };
    const preview = computeDcfPreview(inputs, 2);
    expect(preview).not.toBeNull();
    expect(draftInputsReady(inputs, 2)).toBe(true);
    // Revenue declines with negative growth.
    expect(preview!.years[0].revenue).toBeCloseTo(950, 6);
    expect(preview!.years[1].revenue).toBeCloseTo(902.5, 6);
    // NWC shrinks as revenue falls -> ΔNWC is negative (a cash inflow).
    expect(preview!.years[0].deltaNwc).toBeCloseTo(-1, 6);
    expect(preview!.years[0].ufcf).toBeCloseTo(196.13, 2);
    // Net cash (negative net debt) lifts equity above enterprise value.
    expect(preview!.equityValue!).toBeGreaterThan(preview!.enterpriseValue);
  });

  it("allows negative wacc/terminal growth as long as wacc > g", () => {
    const inputs: DcfDraftInputs = {
      base_revenue: 500,
      wacc: -0.02,
      terminal_growth: -0.05,
      revenue_growth: [0.03],
      ebitda_margin: [0.25],
      da_pct: [0.05],
      tax_rate: [0.21],
      capex_pct: [0.04],
      nwc_pct: [0.02],
    };
    const preview = computeDcfPreview(inputs, 1);
    expect(preview).not.toBeNull();
    expect(Number.isFinite(preview!.enterpriseValue)).toBe(true);
  });

  it("applyAllDefaults fills all forecast rows", () => {
    const inputs: DcfDraftInputs = {
      base_revenue: 100,
      wacc: 0.1,
      terminal_growth: 0.02,
      revenue_growth: [null, null],
      ebitda_margin: [null, null],
      da_pct: [null, null],
      tax_rate: [null, null],
      capex_pct: [null, null],
      nwc_pct: [null, null],
    };
    const filled = applyAllDefaults(
      inputs,
      {
        revenue_growth: 0.08,
        ebitda_margin: 0.3,
        da_pct: 0.04,
        tax_rate: 0.21,
        capex_pct: 0.04,
        nwc_pct: 0.02,
      },
      2,
    );
    expect(filled.revenue_growth).toEqual([0.08, 0.08]);
    expect(filled.ebitda_margin).toEqual([0.3, 0.3]);
    expect(filled.da_pct).toEqual([0.04, 0.04]);
  });
});
