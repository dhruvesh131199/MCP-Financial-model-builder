import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import FetchFinancialsHubPanel from "./FetchFinancialsHubPanel";
import type { FinancialsFetchLogEntry } from "../types";

vi.mock("../api/sessionFinancials", () => ({
  fetchSessionFinancials: vi.fn(),
  isFinancialsInFlight: vi.fn(() => false),
  subscribeFinancialsInFlight: vi.fn(() => () => {}),
}));

import { fetchSessionFinancials } from "../api/sessionFinancials";

const logEntry: FinancialsFetchLogEntry = {
  id: "req-1",
  created_at: "2026-07-02T12:00:00+00:00",
  source: "rest",
  tickers: ["AAPL"],
  years: null,
  max_years: 5,
  status: "success",
  results: [{ ticker: "AAPL", success: true, file_id: "f1" }],
};

function renderPanel(fetchLog: FinancialsFetchLogEntry[] = []) {
  return render(
    <FetchFinancialsHubPanel
      sessionId="sess-1"
      fetchLog={fetchLog}
      onRefresh={vi.fn()}
    />,
  );
}

function addTicker(label: string, value: string) {
  const input = screen.getByPlaceholderText(label);
  fireEvent.change(input, { target: { value } });
  fireEvent.keyDown(input, { key: "Enter" });
}

describe("FetchFinancialsHubPanel", () => {
  beforeEach(() => {
    vi.mocked(fetchSessionFinancials).mockReset();
  });

  it("renders disclaimer and form labels", () => {
    renderPanel();
    expect(screen.getByRole("heading", { name: "Fetch Financials" })).toBeTruthy();
    expect(screen.getByText("Fiscal years (optional, up to 10)")).toBeTruthy();
    expect(screen.getByText("Last N fiscal years (optional)")).toBeTruthy();
  });

  it("shows fill message and enables submit without tickers", () => {
    renderPanel();
    const btn = screen.getByRole("button", { name: "Fetch financials" }) as HTMLButtonElement;
    expect(btn.disabled).toBe(false);
    fireEvent.click(btn);
    expect(screen.getByText("Please fill all required values.")).toBeTruthy();
    expect(fetchSessionFinancials).not.toHaveBeenCalled();
  });

  it("submits tickers with max_years from dropdown", async () => {
    vi.mocked(fetchSessionFinancials).mockResolvedValue({
      request_id: "r1",
      tickers: ["AAPL"],
      years: null,
      max_years: 5,
      status: "success",
      success_count: 1,
      total_count: 1,
      results: [{ ticker: "AAPL", success: true }],
      errors: [],
    });
    renderPanel();
    addTicker("Type ticker and press enter", "AAPL");
    fireEvent.change(screen.getByRole("combobox"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Fetch financials" }));
    await vi.waitFor(() => {
      expect(fetchSessionFinancials).toHaveBeenCalledWith("sess-1", {
        tickers: ["AAPL"],
        years: undefined,
        max_years: 5,
      });
    });
  });

  it("disables last N dropdown when year chips present", () => {
    renderPanel();
    addTicker("Type a year and press enter", "2024");
    const select = screen.getByRole("combobox") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
  });

  it("renders request history", () => {
    renderPanel([logEntry]);
    expect(screen.getByText("Request history")).toBeTruthy();
    expect(screen.getByText("AAPL")).toBeTruthy();
    expect(screen.getByText("Last 5 fiscal years")).toBeTruthy();
  });
});
