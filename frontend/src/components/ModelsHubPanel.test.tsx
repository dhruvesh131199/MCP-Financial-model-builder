import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import ModelsHubPanel from "./ModelsHubPanel";

vi.mock("../api/sessionModels", () => ({
  createSessionDcfModel: vi.fn(),
  createSessionComparativeModel: vi.fn(),
  isModelsInFlight: vi.fn(() => false),
  subscribeModelsInFlight: vi.fn(() => () => {}),
}));

import { createSessionComparativeModel, createSessionDcfModel } from "../api/sessionModels";

describe("ModelsHubPanel", () => {
  it("renders DCF and Comparative toggles", () => {
    render(
      <ModelsHubPanel
        sessionId="sess-1"
        onRefresh={vi.fn()}
        onCreated={vi.fn()}
      />,
    );
    expect(screen.getByText("DCF model")).toBeTruthy();
    expect(screen.getByText("Comparative model")).toBeTruthy();
  });

  it("shows fill message when DCF create clicked without required values", () => {
    render(
      <ModelsHubPanel
        sessionId="sess-1"
        onRefresh={vi.fn()}
        onCreated={vi.fn()}
      />,
    );
    const btn = screen.getByRole("button", { name: "Create template" });
    expect(btn).toHaveProperty("disabled", false);
    fireEvent.click(btn);
    expect(screen.getByText("Please fill all required values.")).toBeTruthy();
    expect(createSessionDcfModel).not.toHaveBeenCalled();
  });

  it("creates DCF and calls onCreated", async () => {
    const onCreated = vi.fn();
    const onRefresh = vi.fn();
    vi.mocked(createSessionDcfModel).mockResolvedValue({
      success: true,
      model_id: "model-abc",
      model_name: "Test DCF",
      projection_years: 5,
      reference_years: 0,
      prefilled: { base_revenue: 100 },
      message: "Created",
    });

    render(
      <ModelsHubPanel
        sessionId="sess-1"
        onRefresh={onRefresh}
        onCreated={onCreated}
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("e.g. Apple 5Y DCF"), {
      target: { value: "Test DCF" },
    });
    fireEvent.change(screen.getByPlaceholderText("e.g. 1000"), {
      target: { value: "100" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create template" }));

    await waitFor(() => {
      expect(createSessionDcfModel).toHaveBeenCalledWith("sess-1", {
        name: "Test DCF",
        projection_years: 5,
        base_revenue: 100,
      });
    });
    expect(onCreated).toHaveBeenCalledWith("model-abc");
    expect(onRefresh).toHaveBeenCalled();
  });

  it("shows fill message when comparative submit clicked without values", () => {
    render(
      <ModelsHubPanel
        sessionId="sess-1"
        onRefresh={vi.fn()}
        onCreated={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Comparative model"));
    const btn = screen.getByRole("button", { name: "Do comparative analysis" });
    expect(btn).toHaveProperty("disabled", false);
    fireEvent.click(btn);
    expect(screen.getByText("Please fill all required values.")).toBeTruthy();
  });

  it("runs comparative analysis and calls onCreated", async () => {
    const onCreated = vi.fn();
    const onRefresh = vi.fn();
    vi.mocked(createSessionComparativeModel).mockResolvedValue({
      success: true,
      model_id: "comp-1",
      model_name: "KO vs PEP",
      fiscal_year_used: 2024,
      message: "Done",
    });

    render(
      <ModelsHubPanel
        sessionId="sess-1"
        onRefresh={onRefresh}
        onCreated={onCreated}
      />,
    );

    fireEvent.click(screen.getByText("Comparative model"));
    fireEvent.change(screen.getByPlaceholderText("e.g. nvda"), {
      target: { value: "KO" },
    });

    const peerInput = screen.getByPlaceholderText("Type ticker and press enter");
    fireEvent.change(peerInput, { target: { value: "PEP" } });
    fireEvent.keyDown(peerInput, { key: "Enter" });

    fireEvent.click(screen.getByRole("button", { name: "Do comparative analysis" }));

    await waitFor(() => {
      expect(createSessionComparativeModel).toHaveBeenCalledWith("sess-1", {
        target: "KO",
        peers: ["PEP"],
      });
    });
    expect(onCreated).toHaveBeenCalledWith("comp-1");
    expect(onRefresh).toHaveBeenCalled();
  });
});
