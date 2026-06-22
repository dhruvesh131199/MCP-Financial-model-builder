import { describe, expect, it } from "vitest";
import {
  comparativeExportCompanyCount,
  comparativeExportRowLabels,
} from "./exportComparativeExcel";
import type { ComparativeReport } from "../types";

const report: ComparativeReport = {
  model_type: "comparative",
  fiscal_year_used: 2024,
  target: { ticker: "KO" },
  peers: [{ ticker: "PEP" }],
  summary: {},
  companies: [
    {
      ticker: "KO",
      is_target: true,
      fundamentals: {},
      market_data: {},
      multiples: {},
    },
    {
      ticker: "PEP",
      is_target: false,
      fundamentals: {},
      market_data: {},
      multiples: {},
    },
  ],
};

describe("exportComparativeExcel helpers", () => {
  it("exports expected row labels", () => {
    const labels = comparativeExportRowLabels(report);
    expect(labels).toContain("Revenue");
    expect(labels).toContain("P/E");
    expect(labels).toContain("EV / EBITDA");
  });

  it("counts companies in report", () => {
    expect(comparativeExportCompanyCount(report)).toBe(2);
  });
});
