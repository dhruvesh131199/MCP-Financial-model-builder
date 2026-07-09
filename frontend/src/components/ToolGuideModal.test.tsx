import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ToolGuideModal from "./ToolGuideModal";
import { MCP_TOOL_GUIDE } from "../config/mcpToolGuide";

describe("ToolGuideModal", () => {
  it("renders all tools in the guide table", () => {
    render(<ToolGuideModal open onClose={vi.fn()} />);

    expect(screen.getByRole("dialog")).toBeTruthy();
    expect(screen.getByRole("heading", { name: /MCP tools guide/i })).toBeTruthy();

    for (const entry of MCP_TOOL_GUIDE) {
      expect(screen.getAllByText(entry.tool).length).toBeGreaterThan(0);
      expect(screen.getByText(entry.summary)).toBeTruthy();
      expect(screen.getByText(entry.examples[0])).toBeTruthy();
    }
  });

  it("calls onClose when backdrop is clicked", () => {
    const onClose = vi.fn();
    render(<ToolGuideModal open onClose={onClose} />);

    fireEvent.click(screen.getByLabelText("Close tool guide"));
    expect(onClose).toHaveBeenCalled();
  });
});
