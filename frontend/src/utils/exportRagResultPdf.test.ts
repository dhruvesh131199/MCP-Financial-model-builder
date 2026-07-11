import { afterEach, describe, expect, it, vi } from "vitest";
import { exportRagResultPdf } from "./exportRagResultPdf";

describe("exportRagResultPdf", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.replaceChildren();
  });

  it("writes content into a hidden iframe and calls print", () => {
    vi.useFakeTimers();
    const print = vi.fn();
    const write = vi.fn();
    const close = vi.fn();
    const focus = vi.fn();
    const open = vi.fn();

    const fakeDoc = {
      open,
      write,
      close,
      readyState: "complete",
    };
    const fakeWin = { focus, print };

    const originalCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreate(tag);
      if (tag.toLowerCase() === "iframe") {
        Object.defineProperty(el, "contentDocument", { get: () => fakeDoc });
        Object.defineProperty(el, "contentWindow", { get: () => fakeWin });
      }
      return el;
    });

    exportRagResultPdf("My Result", "<p>Hello</p>");

    expect(open).toHaveBeenCalled();
    expect(write).toHaveBeenCalled();
    const html = String(write.mock.calls[0][0]);
    expect(html).toContain("My Result");
    expect(html).toContain("<p>Hello</p>");

    vi.advanceTimersByTime(50);
    expect(focus).toHaveBeenCalled();
    expect(print).toHaveBeenCalled();
    vi.useRealTimers();
  });

  it("throws when iframe document is unavailable", () => {
    const originalCreate = document.createElement.bind(document);
    vi.spyOn(document, "createElement").mockImplementation((tag: string) => {
      const el = originalCreate(tag);
      if (tag.toLowerCase() === "iframe") {
        Object.defineProperty(el, "contentDocument", { get: () => null });
        Object.defineProperty(el, "contentWindow", { get: () => null });
      }
      return el;
    });

    expect(() => exportRagResultPdf("X", "<p>y</p>")).toThrow(/Could not prepare print view/);
  });
});
