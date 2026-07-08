import { describe, expect, it } from "vitest";
import type { DcfDraftData } from "../types";

describe("exportDcfTemplateExcel", () => {
  it("module exports template function", async () => {
    const mod = await import("./exportDcfExcel");
    expect(typeof mod.exportDcfTemplateExcel).toBe("function");
    expect(typeof mod.exportDcfToExcel).toBe("function");
  });

  it("draft fixture has decoupled reference vs forecast length", () => {
    const draft: DcfDraftData = {
      type: "dcf_draft",
      ticker: "MU",
      projection_years: 3,
      reference_history: {
        ticker: "MU",
        fiscal_years: [2024, 2023, 2022, 2021, 2020],
        rows: [],
      },
      inputs: {
        base_revenue: null,
        wacc: null,
        terminal_growth: null,
        revenue_growth: [null, null, null],
        ebitda_margin: [null, null, null],
        da_pct: [null, null, null],
        tax_rate: [null, null, null],
        capex_pct: [null, null, null],
        nwc_pct: [null, null, null],
      },
    };
    expect(draft.reference_history.fiscal_years).toHaveLength(5);
    expect(draft.inputs.revenue_growth).toHaveLength(3);
  });
});
