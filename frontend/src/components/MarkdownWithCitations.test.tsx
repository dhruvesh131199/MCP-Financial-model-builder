import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import MarkdownWithCitations from "./MarkdownWithCitations";

vi.mock("../api/sessionRag", () => ({
  getSessionRagParent: vi.fn(),
}));

import { getSessionRagParent } from "../api/sessionRag";

const getParent = vi.mocked(getSessionRagParent);

describe("MarkdownWithCitations", () => {
  beforeEach(() => {
    getParent.mockReset();
    getParent.mockResolvedValue({
      parent_id: "AAPL_2025_10K_P_07",
      document_id: "doc-1",
      ticker: "AAPL",
      year: 2025,
      doctype: "10K",
      chunk_index: 7,
      content: "component cost pressures weighed on margin",
      char_count: 40,
      approx_tokens: 10,
      document_source: "sec_annual",
      label: "AAPL · 10K · FY2025 · section #7",
    });
  });

  it("renders citation chips and opens drawer on click", async () => {
    render(
      <MarkdownWithCitations
        sessionId="sess-1"
        markdown={'Costs rose [[cite:AAPL_2025_10K_P_07|"component cost pressures"]].'}
      />,
    );

    const chip = screen.getByRole("button", {
      name: /Source: component cost pressures/i,
    });
    expect(chip).toBeTruthy();
    fireEvent.click(chip);

    await waitFor(() => {
      expect(getParent).toHaveBeenCalledWith("sess-1", "AAPL_2025_10K_P_07");
    });
    expect(await screen.findByRole("dialog")).toBeTruthy();
    expect(
      screen.getByRole("heading", { name: /AAPL · 10K · FY2025 · section #7/ }),
    ).toBeTruthy();
    expect(screen.getAllByText(/component cost pressures/i).length).toBeGreaterThan(0);
  });
});
