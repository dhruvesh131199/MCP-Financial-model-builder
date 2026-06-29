import type { DashboardSelection, DcfModelEntry, ModelEntry } from "../types";

export function dcfTwinDraftId(model: ModelEntry): string | undefined {
  if (model.type !== "dcf") return undefined;
  const entry = model as DcfModelEntry;
  return entry.draft_id ?? entry.data?.draft_id;
}

/** When a new model appears from polling, never auto-select a hidden DCF twin. */
export function resolveNewModelAutoSelect(
  latest: ModelEntry,
  selection: DashboardSelection,
): { kind: "model"; id: string } | null {
  const twinDraftId = dcfTwinDraftId(latest);
  if (twinDraftId) {
    if (selection.kind === "model" && selection.id === twinDraftId) {
      return null;
    }
    return { kind: "model", id: twinDraftId };
  }
  return { kind: "model", id: latest.id };
}

/** Redirect selection from a hidden valuation twin to its parent draft. */
export function resolveOrphanModelSelection(
  selection: DashboardSelection,
  sidebarModelIds: readonly string[],
  models: ModelEntry[],
): DashboardSelection {
  if (selection.kind !== "model") return selection;
  if (sidebarModelIds.includes(selection.id)) return selection;

  const twin = models.find((m) => m.id === selection.id && m.type === "dcf");
  if (twin) {
    const draftId = dcfTwinDraftId(twin);
    if (draftId) return { kind: "model", id: draftId };
  }

  for (const model of models) {
    if (model.type !== "dcf_draft") continue;
    if (model.data.computed_model_id === selection.id) {
      return { kind: "model", id: model.id };
    }
  }

  return selection;
}
