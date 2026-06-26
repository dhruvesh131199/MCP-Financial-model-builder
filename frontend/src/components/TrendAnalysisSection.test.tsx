import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TrendAnalysisSection from "./TrendAnalysisSection";
import type { TrendAnalysisData } from "../types";

const sampleTrend: TrendAnalysisData = {
  fiscal_years: [2025, 2024],
  rows: [
    {
      key: "revenue",
      label: "Revenue",
      row_type: "currency",
      highlight: false,
      values: [110, 100],
    },
    {
      key: "revenue_growth_yoy",
      label: "Revenue growth YoY %",
      row_type: "percent",
      highlight: true,
      values: [10, null],
    },
  ],
};

describe("TrendAnalysisSection", () => {
  it("renders highlighted rows with semibold styling", () => {
    const { container } = render(<TrendAnalysisSection trend={sampleTrend} />);
    expect(screen.getByText("Trend analysis")).toBeTruthy();
    const growthRow = screen.getByText("Revenue growth YoY %").closest("tr");
    expect(growthRow?.className).toContain("font-semibold");
    expect(growthRow?.className).toContain("bg-slate-50");
    const revenueRow = screen.getByText("Revenue").closest("tr");
    expect(revenueRow?.className).not.toContain("font-semibold");
    expect(container.querySelectorAll("th")).toHaveLength(3);
  });
});
