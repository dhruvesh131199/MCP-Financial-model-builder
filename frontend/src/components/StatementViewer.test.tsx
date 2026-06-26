import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import StatementViewer from "./StatementViewer";
import type { FinancialStatements } from "../types";

function makeFinancials(
  annualCount: number,
  quarterlyCount = 0,
): FinancialStatements {
  const annual = Array.from({ length: annualCount }, (_, i) => ({
    fiscal_year: 2020 + i,
    fiscal_period: "FY",
    period_end: `${2020 + i}-12-31`,
    line_items: [{ key: "revenue", label: "Revenue", value: 100, unit: "USD" }],
  }));
  const quarterly =
    quarterlyCount > 0
      ? Array.from({ length: quarterlyCount }, (_, i) => ({
          fiscal_year: 2025,
          fiscal_period: `Q${i + 1}`,
          period_end: `2025-${(i + 1) * 3}-30`,
          line_items: [{ key: "revenue", label: "Revenue", value: 25, unit: "USD" }],
        }))
      : [];

  return {
    ticker: "TST",
    cik: "1",
    entity_name: "Test Co",
    fetched_at: "2026-01-01T00:00:00+00:00",
    statements: {
      income: { annual, quarterly },
      balance: { annual: [], quarterly: [] },
      cashflow: { annual: [], quarterly: [] },
    },
    fetch_scope: ["income", "balance", "cashflow"],
    ingest_source: "test",
  };
}

describe("StatementViewer", () => {
  it("hides compare tabs for a single annual period", () => {
    render(<StatementViewer financials={makeFinancials(1)} />);
    expect(screen.queryByText(/Compare/i)).toBeNull();
    expect(screen.getByText("Revenue")).toBeTruthy();
  });

  it("shows compare tabs when multiple annual periods exist", () => {
    render(<StatementViewer financials={makeFinancials(2)} />);
    expect(screen.getByText(/Compare/i)).toBeTruthy();
  });

  it("hides quarterly tab when no quarterly data exists", () => {
    render(<StatementViewer financials={makeFinancials(1, 0)} />);
    expect(screen.queryByRole("button", { name: "Quarterly" })).toBeNull();
  });

  it("shows quarterly tab when quarterly data exists", () => {
    render(<StatementViewer financials={makeFinancials(1, 2)} />);
    expect(screen.getByRole("button", { name: "Quarterly" })).toBeTruthy();
  });
});
