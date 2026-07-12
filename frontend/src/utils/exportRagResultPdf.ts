/** Print RAG result HTML via a hidden iframe (no pop-up window). */

const PRINT_STYLES = `
  @page { margin: 16mm; }
  body {
    font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
    color: #1f2937;
    font-size: 12pt;
    line-height: 1.5;
    margin: 0;
    padding: 0;
  }
  h1 { font-size: 18pt; margin: 0 0 4pt; color: #2e1065; }
  .meta { font-size: 9pt; color: #6b7280; margin-bottom: 16pt; }
  h1, h2, h3 { color: #2e1065; }
  h2 { font-size: 14pt; margin: 16pt 0 8pt; }
  h3 { font-size: 12pt; margin: 12pt 0 6pt; }
  p, ul, ol { margin: 0 0 8pt; }
  table {
    width: 100%;
    border-collapse: collapse;
    margin: 10pt 0 14pt;
    font-size: 10pt;
  }
  th, td {
    border: 1px solid #d1d5db;
    padding: 6pt 8pt;
    text-align: left;
    vertical-align: top;
  }
  th { background: #f5f3ff; font-weight: 600; }
  code {
    font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
    font-size: 0.9em;
    background: #f3f4f6;
    padding: 1pt 3pt;
    border-radius: 3pt;
  }
  pre {
    background: #f3f4f6;
    padding: 8pt;
    border-radius: 4pt;
    overflow-x: auto;
    white-space: pre-wrap;
  }
  blockquote {
    margin: 8pt 0;
    padding-left: 10pt;
    border-left: 3pt solid #c4b5fd;
    color: #4b5563;
  }
`;

export function exportRagResultPdf(
  title: string,
  contentHtml: string,
  meta = "Pinned RAG reference · Financial Analyzer",
): void {
  const safeTitle = title.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const safeMeta = meta.replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const iframe = document.createElement("iframe");
  iframe.setAttribute("title", "Print export");
  iframe.style.position = "fixed";
  iframe.style.right = "0";
  iframe.style.bottom = "0";
  iframe.style.width = "0";
  iframe.style.height = "0";
  iframe.style.border = "0";
  iframe.style.opacity = "0";
  iframe.style.pointerEvents = "none";
  document.body.appendChild(iframe);

  const doc = iframe.contentDocument;
  const win = iframe.contentWindow;
  if (!doc || !win) {
    iframe.remove();
    throw new Error("Could not prepare print view for PDF export.");
  }

  doc.open();
  doc.write(`<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${safeTitle}</title>
  <style>${PRINT_STYLES}</style>
</head>
<body>
  <h1>${safeTitle}</h1>
  <p class="meta">${safeMeta}</p>
  ${contentHtml}
</body>
</html>`);
  doc.close();

  const cleanup = () => {
    iframe.remove();
  };

  const triggerPrint = () => {
    try {
      win.focus();
      win.print();
    } finally {
      // Delay removal so the print dialog can snapshot the document.
      window.setTimeout(cleanup, 1000);
    }
  };

  if (doc.readyState === "complete") {
    window.setTimeout(triggerPrint, 50);
  } else {
    iframe.addEventListener("load", () => window.setTimeout(triggerPrint, 50), {
      once: true,
    });
  }
}
