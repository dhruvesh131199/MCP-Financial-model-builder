import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import ComparativeTable from "./ComparativeTable";
import type { ComparativeReport } from "../types";

const sampleReport: ComparativeReport = {
  model_type: "comparative",
  fiscal_year_used: 2024,
  fiscal_year_note: "Test note",
  target: { ticker: "KO" },
  peers: [{ ticker: "PEP" }],
  market_data_errors: ["PEP"],
  summary: {
    peer_median_pe: 20,
    peer_median_ev_to_sales: 5,
    peer_median_ev_to_ebitda: 15,
    peer_median_net_margin: 0.12,
  },
  companies: [
    {
      ticker: "KO",
      company_name: "Coca-Cola",
      is_target: true,
      fundamentals: { revenue: 1e9, net_margin: 0.15 },
      market_data: { stock_price: 60, as_of: "2026-01-01" },
      multiples: { stock_price: 60, pe_ratio: 25, ev_to_ebitda: null },
    },
    {
      ticker: "PEP",
      company_name: "PepsiCo",
      is_target: false,
      fundamentals: { revenue: 8e8, net_margin: 0.1 },
      market_data: {},
      multiples: { pe_ratio: null },
    },
  ],
};

describe("ComparativeTable", () => {
  it("highlights target and shows peer median summary", () => {
    render(<ComparativeTable report={sampleReport} />);
    expect(screen.getByText("Target")).toBeTruthy();
    expect(screen.getByText("Peer median P/E")).toBeTruthy();
    expect(screen.getByText("Market data unavailable")).toBeTruthy();
    expect(screen.getAllByText(/PEP/).length).toBeGreaterThan(0);
  });

  it("shows SEC warning and host LLM prompt with tickers", () => {
    render(<ComparativeTable report={sampleReport} />);
    expect(screen.getByText(/SEC data — mapping may be inaccurate/)).toBeTruthy();
    expect(screen.getByText(/Ask your host LLM/)).toBeTruthy();
    expect(screen.getByText(/KO and PEP/)).toBeTruthy();
    expect(screen.getByText(/rag_res_on_display/)).toBeTruthy();
  });

  it("shows dash for null Tier B multiples", () => {
    render(<ComparativeTable report={sampleReport} />);
    const dashes = screen.getAllByText("—");
    expect(dashes.length).toBeGreaterThan(0);
  });
});
