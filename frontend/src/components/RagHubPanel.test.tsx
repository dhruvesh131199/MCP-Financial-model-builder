import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import RagHubPanel from "./RagHubPanel";
import type { RagDocumentEntry } from "../types";

vi.mock("../api/sessionRag", () => ({
  fetchSessionRag: vi.fn(),
  isRagInFlight: vi.fn(() => false),
  subscribeRagInFlight: vi.fn(() => () => {}),
  uploadSessionRag: vi.fn(),
  sessionRagChunksPath: (sessionId: string, documentId: string) =>
    `/s/${sessionId}/rag/${documentId}/chunks`,
  sessionRagRawHref: () => "http://localhost:8000/api/sessions/sess-1/rag/documents/doc-uuid-1/raw",
}));

import { uploadSessionRag } from "../api/sessionRag";

const readyDoc: RagDocumentEntry = {
  id: "entry-1",
  filing_key: "AAPL_2025_10K",
  document_id: "doc-uuid-1",
  ticker: "AAPL",
  year: 2025,
  doctype: "10K",
  label: "AAPL · 10-K · FY2025",
  source: "sec_annual",
  status: "ready",
  error: null,
  from_cache: false,
  raw_url: "/api/sessions/sess-1/rag/documents/doc-uuid-1/raw",
  report_url: "/api/sessions/sess-1/rag/documents/doc-uuid-1/report",
  chunks_url: "/api/sessions/sess-1/rag/documents/doc-uuid-1/chunks",
  has_report: true,
};

const errorDoc: RagDocumentEntry = {
  id: "entry-2",
  filing_key: "error_abc123",
  document_id: null,
  ticker: "BAD",
  year: null,
  doctype: null,
  label: "BAD 10-K",
  source: "sec_annual",
  status: "error",
  error: "SEC fetch failed",
  from_cache: false,
};

function renderPanel(documents: RagDocumentEntry[]) {
  return render(
    <MemoryRouter>
      <RagHubPanel
        sessionId="sess-1"
        documents={documents}
        onRefresh={vi.fn()}
      />
    </MemoryRouter>,
  );
}

describe("RagHubPanel", () => {
  it("renders chat example and RAG badge", () => {
    renderPanel([]);
    expect(screen.getByText(/Ask in chat/i)).toBeTruthy();
    expect(screen.getByText(/Fetch Walmart 2024 annual report/i)).toBeTruthy();
    expect(screen.getByText("RAG")).toBeTruthy();
  });

  it("shows ready doc with Done, View chunks, and View 10-K links", () => {
    renderPanel([readyDoc]);
    expect(screen.getByText("Done")).toBeTruthy();
    const chunksLink = screen.getByText("View chunks");
    expect(chunksLink.getAttribute("target")).toBe("_blank");
    const reportLink = screen.getByText("View 10-K");
    expect(reportLink.getAttribute("target")).toBe("_blank");
    expect(reportLink.getAttribute("href")).toContain("/raw");
  });

  it("does not upload until Upload button clicked", () => {
    renderPanel([]);
    fireEvent.click(screen.getByText("Upload"));
    const file = new File(["html"], "test.html", { type: "text/html" });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    expect(uploadSessionRag).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Upload file" }));
    expect(uploadSessionRag).toHaveBeenCalled();
  });

  it("shows error row with message", () => {
    renderPanel([errorDoc]);
    expect(screen.getByText("Error")).toBeTruthy();
    expect(screen.getByText("SEC fetch failed")).toBeTruthy();
  });
});
