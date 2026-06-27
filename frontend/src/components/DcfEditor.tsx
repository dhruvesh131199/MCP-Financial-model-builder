import { useEffect, useMemo, useState } from "react";
import type { DcfDraftData, DcfDraftDefaults, DcfDraftInputs, DcfResult } from "../types";
import { computeDcfDraft, patchDcfDraft } from "../api";
import {
  applyAllDefaults,
  computeDcfPreview,
  draftInputsReady,
} from "../lib/dcfCompute";
import { exportDcfTemplateExcel, exportDcfToExcel } from "../utils/exportDcfExcel";
import DcfAssumptionsForm from "./DcfAssumptionsForm";
import DcfForecastGrid from "./DcfForecastGrid";
import DcfReferencePanel from "./DcfReferencePanel";
import DcfTable from "./DcfTable";

type EditorView = "template" | "valuation";

interface DcfEditorProps {
  sessionId: string;
  modelId: string;
  draft: DcfDraftData;
  modelName: string;
  computedResult?: DcfResult | null;
}

export default function DcfEditor({
  sessionId,
  modelId,
  draft,
  modelName,
  computedResult,
}: DcfEditorProps) {
  const [view, setView] = useState<EditorView>("template");
  const [inputs, setInputs] = useState<DcfDraftInputs>(() => ({
    ...draft.inputs,
  }));
  const [defaults, setDefaults] = useState<DcfDraftDefaults>(
    () => draft.defaults ?? {},
  );
  const [saving, setSaving] = useState(false);
  const [computing, setComputing] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [localComputed, setLocalComputed] = useState<DcfResult | null>(
    computedResult ?? null,
  );

  useEffect(() => {
    setLocalComputed(computedResult ?? null);
  }, [computedResult]);

  useEffect(() => {
    setInputs({ ...draft.inputs });
    setDefaults(draft.defaults ?? {});
  }, [draft]);

  const preview = useMemo(
    () => computeDcfPreview(inputs, draft.projection_years),
    [inputs, draft.projection_years],
  );

  const ready = draftInputsReady(inputs, draft.projection_years);
  const hasValuation = localComputed != null;

  function mergeInputs(patch: Partial<DcfDraftInputs>) {
    setInputs((prev) => ({ ...prev, ...patch }));
    setSuccess(null);
  }

  function fillForecastRows() {
    setInputs((prev) => applyAllDefaults(prev, defaults, draft.projection_years));
    setSuccess(null);
  }

  async function handleUpdate() {
    setError(null);
    setSuccess(null);
    if (!ready) {
      setError("Fill all required fields before updating the model.");
      return;
    }
    setSaving(true);
    try {
      await patchDcfDraft(sessionId, modelId, { ...inputs, defaults });
      setComputing(true);
      const result = await computeDcfDraft(sessionId, modelId);
      setLocalComputed(result.result);
      setView("valuation");
      setSuccess(
        `Valuation updated — EV $${result.enterprise_value_millions.toFixed(1)}M`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setSaving(false);
      setComputing(false);
    }
  }

  async function handleDownloadTemplate() {
    setDownloading(true);
    try {
      await exportDcfTemplateExcel({ ...draft, inputs, defaults }, modelName);
    } finally {
      setDownloading(false);
    }
  }

  async function handleDownloadValuation() {
    if (!localComputed) return;
    setDownloading(true);
    try {
      await exportDcfToExcel(localComputed, modelName);
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <div className="shrink-0 border-b border-gray-200 bg-gradient-to-r from-white to-indigo-50/40 px-4 py-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold text-indigo-950">
              {draft.ticker} DCF — {draft.projection_years}-year forecast
            </h2>
            <p className="text-xs text-gray-500">5-year SEC reference · Units: $M USD</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="flex rounded-lg border border-indigo-200 bg-white p-0.5 text-xs">
              <button
                type="button"
                onClick={() => setView("template")}
                className={`rounded-md px-3 py-1 font-medium ${
                  view === "template"
                    ? "bg-indigo-600 text-white"
                    : "text-indigo-700 hover:bg-indigo-50"
                }`}
              >
                Template
              </button>
              <button
                type="button"
                onClick={() => hasValuation && setView("valuation")}
                disabled={!hasValuation}
                className={`rounded-md px-3 py-1 font-medium ${
                  view === "valuation"
                    ? "bg-indigo-600 text-white"
                    : "text-indigo-700 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-40"
                }`}
              >
                Valuation
              </button>
            </div>
            {view === "template" ? (
              <>
                <button
                  type="button"
                  onClick={handleDownloadTemplate}
                  disabled={downloading}
                  className="rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
                >
                  {downloading ? "Exporting…" : "Download template"}
                </button>
                <button
                  type="button"
                  onClick={handleUpdate}
                  disabled={saving || computing}
                  className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
                >
                  {computing ? "Computing…" : saving ? "Saving…" : "Update model"}
                </button>
              </>
            ) : (
              <button
                type="button"
                onClick={handleDownloadValuation}
                disabled={downloading || !localComputed}
                className="rounded-lg border border-indigo-200 bg-white px-3 py-1.5 text-xs font-medium text-indigo-700 hover:bg-indigo-50 disabled:opacity-50"
              >
                {downloading ? "Exporting…" : "Download .xlsx"}
              </button>
            )}
          </div>
        </div>
        {error && (
          <p className="mt-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
            {error}
          </p>
        )}
        {success && (
          <p className="mt-2 rounded-lg border border-green-200 bg-green-50 px-3 py-2 text-xs text-green-800">
            {success}
          </p>
        )}
      </div>

      {view === "valuation" && localComputed ? (
        <div className="min-h-0 flex-1 overflow-hidden">
          <DcfTable model={localComputed} />
        </div>
      ) : (
        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
          <DcfReferencePanel reference={draft.reference_history} />
          <DcfAssumptionsForm
            inputs={inputs}
            defaults={defaults}
            onChange={mergeInputs}
            onDefaultsChange={setDefaults}
            onFillForecastRows={fillForecastRows}
          />
          <DcfForecastGrid
            projectionYears={draft.projection_years}
            inputs={inputs}
            preview={preview}
            onChange={mergeInputs}
          />
        </div>
      )}
    </div>
  );
}
