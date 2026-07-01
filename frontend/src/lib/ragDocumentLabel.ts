/** Display label for a session RAG document row. */
export function ragDocumentDisplayLabel(doc: {
  label?: string | null;
  filing_key?: string | null;
  ticker?: string | null;
  year?: number | null;
  doctype?: string | null;
}): string {
  if (doc.label?.trim()) return doc.label.trim();
  if (doc.filing_key?.trim()) return doc.filing_key.trim();
  if (doc.ticker && doc.year && doc.doctype) {
    const form = doc.doctype === "10K" ? "10-K" : doc.doctype;
    return `${doc.ticker} · ${form} · FY${doc.year}`;
  }
  return "Document";
}
