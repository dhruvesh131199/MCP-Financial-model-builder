import { describe, expect, it } from "vitest";
import {
  citeDisplayNumbers,
  parseCiteMarker,
  parseCitationHref,
  rewriteCiteMarkersToLinks,
} from "./citeMarkers";

describe("citeMarkers", () => {
  it("parses bare cite", () => {
    expect(parseCiteMarker("[[cite:AAPL_2025_10K_P_07]]")).toEqual({
      parentId: "AAPL_2025_10K_P_07",
    });
  });

  it("parses cite with quote", () => {
    expect(
      parseCiteMarker('[[cite:AAPL_2025_10K_P_07|"component cost pressures"]]'),
    ).toEqual({
      parentId: "AAPL_2025_10K_P_07",
      quote: "component cost pressures",
    });
  });

  it("ignores malformed markers", () => {
    expect(parseCiteMarker("[[cite:]]")).toBeNull();
    expect(parseCiteMarker("[[cite:bad id]]")).toBeNull();
    expect(parseCiteMarker("[cite:AAPL_2025_10K_P_07]")).toBeNull();
  });

  it("rewrites multiple cites to citation hash links", () => {
    const md =
      'Margin fell [[cite:AAPL_2025_10K_P_07]] and costs [[cite:AAPL_2025_10K_P_07|"component cost pressures"]].';
    const out = rewriteCiteMarkersToLinks(md);
    expect(out).toContain("[§](#cite=AAPL_2025_10K_P_07)");
    expect(out).toContain("#cite=AAPL_2025_10K_P_07&quote=");
    expect(out).toContain(encodeURIComponent("component cost pressures"));
  });

  it("assigns display numbers by first appearance", () => {
    const md =
      "One [[cite:A_P_01]] two [[cite:B_P_02]] again [[cite:A_P_01]].";
    const nums = citeDisplayNumbers(md);
    expect(nums.get("A_P_01")).toBe(1);
    expect(nums.get("B_P_02")).toBe(2);
  });

  it("parses citation hrefs", () => {
    expect(parseCitationHref("#cite=AAPL_2025_10K_P_07")).toEqual({
      parentId: "AAPL_2025_10K_P_07",
    });
    expect(
      parseCitationHref(
        `#cite=AAPL_2025_10K_P_07&quote=${encodeURIComponent("hello")}`,
      ),
    ).toEqual({ parentId: "AAPL_2025_10K_P_07", quote: "hello" });
    expect(parseCitationHref("https://example.com")).toBeNull();
  });
});
