import { describe, expect, it } from "vitest";
import { findQuoteRange } from "./citeHighlight";

describe("findQuoteRange", () => {
  const content =
    "Gross margin decreased due to Services and higher cost products.\n\nComponent cost pressures also weighed on results.";

  it("finds exact substring case-insensitively", () => {
    expect(findQuoteRange(content, "component cost pressures")).toEqual({
      start: content.toLowerCase().indexOf("component cost pressures"),
      end:
        content.toLowerCase().indexOf("component cost pressures") +
        "component cost pressures".length,
    });
  });

  it("finds phrase across odd whitespace", () => {
    const messy = "Services   and\nhigher cost products sold well.";
    const range = findQuoteRange(messy, "Services and higher cost products");
    expect(range).not.toBeNull();
    expect(messy.slice(range!.start, range!.end).replace(/\s+/g, " ")).toMatch(
      /Services and higher cost products/i,
    );
  });

  it("falls back to a contiguous word phrase when full quote missing", () => {
    const range = findQuoteRange(
      content,
      "Services and higher cost products which we do not have verbatim",
    );
    expect(range).not.toBeNull();
    expect(content.slice(range!.start, range!.end)).toMatch(
      /Services and higher cost products/i,
    );
  });

  it("returns null when nothing matches", () => {
    expect(findQuoteRange(content, "completely unrelated moon cheese")).toBeNull();
  });
});
