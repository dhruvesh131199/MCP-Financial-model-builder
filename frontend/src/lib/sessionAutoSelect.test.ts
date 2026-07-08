import { describe, expect, it } from "vitest";
import type { DcfModelEntry, ModelEntry } from "../types";
import {
  dcfTwinDraftId,
  resolveNewModelAutoSelect,
  resolveOrphanModelSelection,
} from "./sessionAutoSelect";

function twin(id: string, draftId: string): DcfModelEntry {
  return {
    id,
    name: "WMT DCF",
    type: "dcf",
    created_at: "2026-01-01",
    draft_id: draftId,
    data: { draft_id: draftId } as DcfModelEntry["data"],
  };
}

describe("sessionAutoSelect", () => {
  it("detects twin draft id", () => {
    expect(dcfTwinDraftId(twin("twin-1", "draft-1"))).toBe("draft-1");
  });

  it("keeps draft selected when twin is appended", () => {
    const latest = twin("twin-1", "draft-1");
    const selection = { kind: "model" as const, id: "draft-1" };
    expect(resolveNewModelAutoSelect(latest, selection)).toBeNull();
  });

  it("selects parent draft when twin is appended and nothing selected", () => {
    const latest = twin("twin-1", "draft-1");
    expect(resolveNewModelAutoSelect(latest, { kind: "none" })).toEqual({
      kind: "model",
      id: "draft-1",
    });
  });

  it("selects normal model when latest is not a twin", () => {
    const latest = {
      id: "comp-1",
      name: "Peers",
      type: "comparative",
      created_at: "2026-01-01",
      data: { companies: [], generated_at: "" },
    } as unknown as ModelEntry;
    expect(resolveNewModelAutoSelect(latest, { kind: "none" })).toEqual({
      kind: "model",
      id: "comp-1",
    });
  });

  it("redirects hidden twin selection to draft", () => {
    const models = [
      {
        id: "draft-1",
        name: "WMT draft",
        type: "dcf_draft",
        created_at: "2026-01-01",
        data: {
          type: "dcf_draft",
          ticker: "WMT",
          projection_years: 5,
          inputs: {
            base_revenue: 100,
            wacc: 0.1,
            terminal_growth: 0.02,
            revenue_growth: [0.05],
            ebitda_margin: [0.2],
            da_pct: [0.04],
            tax_rate: [0.21],
            capex_pct: [0.03],
            nwc_pct: [0.01],
          },
          reference_history: { ticker: "WMT", fiscal_years: [], rows: [] },
        },
      },
      twin("twin-1", "draft-1"),
    ] as ModelEntry[];
    expect(
      resolveOrphanModelSelection(
        { kind: "model", id: "twin-1" },
        ["draft-1"],
        models,
      ),
    ).toEqual({ kind: "model", id: "draft-1" });
  });

  it("redirects via computed_model_id when twin lacks draft_id", () => {
    const models = [
      {
        id: "draft-1",
        name: "WMT draft",
        type: "dcf_draft",
        created_at: "2026-01-01",
        data: {
          type: "dcf_draft",
          ticker: "WMT",
          projection_years: 5,
          computed_model_id: "twin-1",
          inputs: {
            base_revenue: 100,
            wacc: 0.1,
            terminal_growth: 0.02,
            revenue_growth: [0.05],
            ebitda_margin: [0.2],
            da_pct: [0.04],
            tax_rate: [0.21],
            capex_pct: [0.03],
            nwc_pct: [0.01],
          },
          reference_history: { ticker: "WMT", fiscal_years: [], rows: [] },
        },
      },
      {
        id: "twin-1",
        name: "WMT DCF",
        type: "dcf",
        created_at: "2026-01-01",
        data: {} as DcfModelEntry["data"],
      },
    ] as ModelEntry[];
    expect(
      resolveOrphanModelSelection(
        { kind: "model", id: "twin-1" },
        ["draft-1"],
        models,
      ),
    ).toEqual({ kind: "model", id: "draft-1" });
  });
});
