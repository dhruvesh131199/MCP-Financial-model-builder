import { describe, expect, it } from "vitest";
import { ragDocumentDisplayLabel } from "./ragDocumentLabel";

describe("ragDocumentDisplayLabel", () => {
  it("prefers label when set", () => {
    expect(
      ragDocumentDisplayLabel({
        label: "AAPL · 10-K · FY2025",
        filing_key: "AAPL_2025_10K",
      }),
    ).toBe("AAPL · 10-K · FY2025");
  });

  it("falls back to filing_key", () => {
    expect(ragDocumentDisplayLabel({ filing_key: "MSFT_2024_10K" })).toBe(
      "MSFT_2024_10K",
    );
  });

  it("builds friendly label from ticker year doctype", () => {
    expect(
      ragDocumentDisplayLabel({ ticker: "AAPL", year: 2025, doctype: "10K" }),
    ).toBe("AAPL · 10-K · FY2025");
  });
});
