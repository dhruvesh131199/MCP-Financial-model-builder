import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ChipInput from "./ChipInput";

describe("ChipInput", () => {
  it("adds chip on Enter", () => {
    const onChange = vi.fn();
    render(<ChipInput values={[]} onChange={onChange} placeholder="Add ticker" />);
    const input = screen.getByPlaceholderText("Add ticker");
    fireEvent.change(input, { target: { value: "aapl" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["aapl"]);
  });

  it("removes last chip on Backspace when input empty", () => {
    const onChange = vi.fn();
    render(<ChipInput values={["AAPL", "NVDA"]} onChange={onChange} />);
    const input = screen.getByRole("textbox");
    fireEvent.keyDown(input, { key: "Backspace" });
    expect(onChange).toHaveBeenCalledWith(["AAPL"]);
  });

  it("removes chip when × clicked", () => {
    const onChange = vi.fn();
    render(<ChipInput values={["AAPL"]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText("Remove AAPL"));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("normalizes and uppercases tickers", () => {
    const onChange = vi.fn();
    render(
      <ChipInput
        values={[]}
        onChange={onChange}
        normalize={(raw) => raw.trim().toUpperCase()}
        placeholder="Ticker"
      />,
    );
    const input = screen.getByPlaceholderText("Ticker");
    fireEvent.change(input, { target: { value: "nvda" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).toHaveBeenCalledWith(["NVDA"]);
  });

  it("blocks add when maxItems reached", () => {
    const onChange = vi.fn();
    render(<ChipInput values={["A", "B"]} onChange={onChange} maxItems={2} />);
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "C" } });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onChange).not.toHaveBeenCalled();
    expect(screen.getByText("Maximum 2 items")).toBeTruthy();
  });

  it("applies error border when error prop set", () => {
    const { container } = render(
      <ChipInput values={[]} onChange={vi.fn()} error />,
    );
    expect(container.querySelector(".border-red-400")).toBeTruthy();
  });
});
