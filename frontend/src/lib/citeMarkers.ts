/**
 * Inline citation markers for pinned RAG / DA narrative markdown.
 *
 * Formats:
 *   [[cite:PARENT_ID]]
 *   [[cite:PARENT_ID|"optional quote to highlight"]]
 *
 * Rewritten to markdown hash links (`#cite=…`) so react-markdown keeps the href
 * (custom schemes like citation:// are stripped by the default url transform).
 */

export interface CiteMarker {
  parentId: string;
  quote?: string;
}

/** Matches [[cite:ID]] or [[cite:ID|"quote"]]. */
export const CITE_MARKER_RE =
  /\[\[cite:([A-Za-z0-9_]+)(?:\|"((?:\\.|[^"\\])*)")?\]\]/g;

const CITE_HASH_PREFIX = "#cite=";

export function parseCiteMarker(raw: string): CiteMarker | null {
  const re = new RegExp(`^${CITE_MARKER_RE.source}$`);
  const m = re.exec(raw.trim());
  if (!m) return null;
  const parentId = m[1];
  const quoteRaw = m[2];
  if (quoteRaw === undefined) return { parentId };
  return { parentId, quote: unescapeQuote(quoteRaw) };
}

function unescapeQuote(q: string): string {
  return q.replace(/\\"/g, '"').replace(/\\\\/g, "\\");
}

/**
 * Rewrite [[cite:…]] markers to markdown links `#cite=parentId&quote=…`
 * so react-markdown can render them via a custom `a` component.
 */
export function rewriteCiteMarkersToLinks(markdown: string): string {
  return markdown.replace(CITE_MARKER_RE, (_full, parentId: string, quoteRaw?: string) => {
    let href = `${CITE_HASH_PREFIX}${encodeURIComponent(parentId)}`;
    if (quoteRaw !== undefined) {
      href += `&quote=${encodeURIComponent(unescapeQuote(quoteRaw))}`;
    }
    return `[§](${href})`;
  });
}

export function isCitationHref(href: string | undefined | null): boolean {
  return Boolean(href?.startsWith(CITE_HASH_PREFIX));
}

export function parseCitationHref(href: string): CiteMarker | null {
  if (!isCitationHref(href)) return null;
  const rest = href.slice(CITE_HASH_PREFIX.length);
  const amp = rest.indexOf("&");
  const idPart = amp >= 0 ? rest.slice(0, amp) : rest;
  const parentId = decodeURIComponent(idPart);
  if (!parentId) return null;

  let quote: string | undefined;
  if (amp >= 0) {
    const params = new URLSearchParams(rest.slice(amp + 1));
    const q = params.get("quote");
    if (q) quote = q;
  }
  return quote !== undefined ? { parentId, quote } : { parentId };
}

/** Assign stable 1-based display numbers by first appearance of each parent_id. */
export function citeDisplayNumbers(markdown: string): Map<string, number> {
  const map = new Map<string, number>();
  const re = new RegExp(CITE_MARKER_RE.source, "g");
  let m: RegExpExecArray | null;
  while ((m = re.exec(markdown)) !== null) {
    const id = m[1];
    if (!map.has(id)) map.set(id, map.size + 1);
  }
  return map;
}
