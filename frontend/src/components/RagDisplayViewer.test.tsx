import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import RagDisplayViewer from "./RagDisplayViewer";
import type { RagDisplayModelEntry } from "../types";

const sampleEntry: RagDisplayModelEntry = {
  id: "rag-1",
  name: "AAPL 10-K DCF metrics",
  type: "rag_display",
  created_at: "2026-01-01T00:00:00+00:00",
  data: {
    content_md: [
      "## Revenue",
      "",
      "| FY | $M |",
      "|----|-----|",
      "| 2025 | 391,035 |",
      "",
      "**Sources:** AAPL · 10-K · FY2025 · §8",
    ].join("\n"),
  },
};

describe("RagDisplayViewer", () => {
  it("renders title and markdown table content", () => {
    render(<RagDisplayViewer entry={sampleEntry} sessionId="sess-1" />);

    expect(screen.getByRole("heading", { name: "AAPL 10-K DCF metrics" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Revenue" })).toBeTruthy();
    expect(screen.getByText("391,035")).toBeTruthy();
    expect(screen.getByText(/Sources:/)).toBeTruthy();
    expect(screen.getByText("Pinned from chat · RAG reference")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Export PDF" })).toBeTruthy();
  });
});
