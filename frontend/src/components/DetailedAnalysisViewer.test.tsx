import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import DetailedAnalysisViewer from "./DetailedAnalysisViewer";
import type { DetailedAnalysisData } from "../types";

const sampleAnalysis: DetailedAnalysisData = {
  ticker: "AAPL",
  entity_name: "Apple Inc.",
  cik: "0000320193",
  fetched_at: "2026-01-01T00:00:00+00:00",
  source: "test",
  warnings: [],
  is_bank_style: false,
  integrity_checks: ["Sample integrity note"],
  periods: [
    {
      fiscal_year: 2025,
      fiscal_period: "FY",
      period_end: "2025-09-27",
      income: [{ key: "revenue", label: "Revenue", value: 100 }],
      balance: [{ key: "total_assets", label: "Total Assets", value: 200 }],
      cashflow: [{ key: "operating_cash_flow", label: "OCF", value: 50 }],
      accounting_equation_ok: true,
    },
  ],
};

describe("DetailedAnalysisViewer", () => {
  it("renders report sections without statement tab buttons", () => {
    render(<DetailedAnalysisViewer analysis={sampleAnalysis} />);

    expect(
      screen.getByRole("heading", {
        name: /AAPL detailed analysis — last 1 year/i,
      }),
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Income Statement" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Balance Sheet" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Cash Flow" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Income Statement" })).toBeNull();
    expect(screen.getByText("Sample integrity note")).toBeTruthy();
  });
});
