import StatementViewer from "./StatementViewer";

interface FileViewerProps {
  file: import("../types").FileEntry;
  hasDetailedAnalysis?: boolean;
}

export default function FileViewer({
  file,
  hasDetailedAnalysis = false,
}: FileViewerProps) {
  if (file.type === "financials") {
    return (
      <div className="flex h-full flex-col">
        {hasDetailedAnalysis && (
          <p className="border-b border-indigo-100 bg-indigo-50/50 px-4 py-2 text-xs text-indigo-800">
            Curated 5-year Detailed Analysis is available in the{" "}
            <strong>Detailed Analysis</strong> sidebar section for this ticker.
          </p>
        )}
        <StatementViewer financials={file.data} />
      </div>
    );
  }
  return null;
}
