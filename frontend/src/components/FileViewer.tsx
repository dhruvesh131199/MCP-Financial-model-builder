import type { FileEntry } from "../types";
import StatementViewer from "./StatementViewer";

interface FileViewerProps {
  file: FileEntry;
}

export default function FileViewer({ file }: FileViewerProps) {
  if (file.type === "financials") {
    return <StatementViewer financials={file.data} />;
  }
  return (
    <p className="p-4 text-sm text-gray-400">Unsupported file type.</p>
  );
}
