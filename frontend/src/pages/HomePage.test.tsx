import { describe, expect, it, vi, beforeEach } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import HomePage from "./HomePage";

const mockNavigate = vi.fn();

vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual<typeof import("react-router-dom")>("react-router-dom");
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("../api", () => ({
  createSession: vi.fn(),
}));

import { createSession } from "../api";

describe("HomePage", () => {
  beforeEach(() => {
    mockNavigate.mockReset();
    vi.mocked(createSession).mockReset();
    Object.defineProperty(HTMLMediaElement.prototype, "play", {
      configurable: true,
      writable: true,
      value: vi.fn().mockResolvedValue(undefined),
    });
  });

  it("renders MCP setup and explore paths", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1, name: /Financial Analyzer Workspace/i })).toBeTruthy();
    expect(screen.getByText(/Create MCP setup/i)).toBeTruthy();
    expect(screen.getByRole("link", { name: /Set up in 1 minute/i })).toBeTruthy();
    expect(screen.getByText(/Start exploring without MCP setup/i)).toBeTruthy();
    expect(screen.getByRole("button", { name: /Start exploring/i })).toBeTruthy();
  });

  it("renders Examples panel with demo video title", () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: /^Examples$/i })).toBeTruthy();
    expect(screen.getByText(/Live RAG \+ Query from 10k reports/i)).toBeTruthy();
  });

  it("creates session and navigates on Start exploring", async () => {
    vi.mocked(createSession).mockResolvedValue({
      session_id: "11111111-2222-3333-4444-555555555555",
      view_url: "http://localhost:5173/s/11111111-2222-3333-4444-555555555555",
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>,
    );

    fireEvent.click(screen.getByRole("button", { name: /Start exploring/i }));

    await waitFor(() => {
      expect(createSession).toHaveBeenCalled();
      expect(mockNavigate).toHaveBeenCalledWith("/s/11111111-2222-3333-4444-555555555555");
    });
  });
});
