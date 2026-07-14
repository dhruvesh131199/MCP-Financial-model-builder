/**
 * Locate a citation quote inside parent-chunk text (exact, then looser fallbacks).
 * Used to wrap a <mark> in the rendered drawer and scroll it into view.
 */

export interface QuoteRange {
  start: number;
  end: number;
}

/** Collapse whitespace; map[i] = original index of collapsed char i. */
function collapseWithMap(original: string): { collapsed: string; map: number[] } {
  const map: number[] = [];
  let collapsed = "";
  let i = 0;
  while (i < original.length && /\s/.test(original[i]!)) i++;
  while (i < original.length) {
    if (/\s/.test(original[i]!)) {
      while (i < original.length && /\s/.test(original[i]!)) i++;
      if (i < original.length && collapsed.length > 0 && !collapsed.endsWith(" ")) {
        collapsed += " ";
        map.push(i - 1);
      }
    } else {
      collapsed += original[i];
      map.push(i);
      i++;
    }
  }
  return { collapsed, map };
}

function rangeFromCollapsedMap(
  map: number[],
  cStart: number,
  cEnd: number,
): QuoteRange | null {
  if (cStart < 0 || cEnd <= cStart || cStart >= map.length) return null;
  const start = map[cStart]!;
  const end = cEnd <= map.length ? map[cEnd - 1]! + 1 : map[map.length - 1]! + 1;
  if (end <= start) return null;
  return { start, end };
}

export function findQuoteRange(content: string, quote: string | undefined): QuoteRange | null {
  const needle = quote?.trim();
  if (!needle || !content) return null;

  const lower = content.toLowerCase();
  const exact = lower.indexOf(needle.toLowerCase());
  if (exact >= 0) return { start: exact, end: exact + needle.length };

  const { collapsed, map } = collapseWithMap(content);
  const collapsedNeedle = needle.replace(/\s+/g, " ").trim();
  const cIdx = collapsed.toLowerCase().indexOf(collapsedNeedle.toLowerCase());
  if (cIdx >= 0) {
    const range = rangeFromCollapsedMap(map, cIdx, cIdx + collapsedNeedle.length);
    if (range) return range;
  }

  const words = collapsedNeedle.split(" ").filter(Boolean);
  if (words.length >= 3) {
    for (let len = Math.min(words.length, 14); len >= 3; len--) {
      for (let offset = 0; offset + len <= words.length; offset++) {
        const phrase = words.slice(offset, offset + len).join(" ");
        const idx = lower.indexOf(phrase.toLowerCase());
        if (idx >= 0) return { start: idx, end: idx + phrase.length };
        const cPhraseIdx = collapsed.toLowerCase().indexOf(phrase.toLowerCase());
        if (cPhraseIdx >= 0) {
          const range = rangeFromCollapsedMap(map, cPhraseIdx, cPhraseIdx + phrase.length);
          if (range) return range;
        }
      }
    }
  }

  return null;
}

/**
 * Wrap the first matching text range in `root` with <mark class="cite-highlight">.
 * Returns the mark element, or null if not found.
 */
export function highlightQuoteInElement(
  root: HTMLElement,
  quote: string | undefined,
): HTMLElement | null {
  root.querySelectorAll("mark.cite-highlight").forEach((el) => {
    const parent = el.parentNode;
    if (!parent) return;
    while (el.firstChild) parent.insertBefore(el.firstChild, el);
    parent.removeChild(el);
    parent.normalize();
  });

  const needle = quote?.trim();
  if (!needle) return null;

  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  let node = walker.nextNode();
  while (node) {
    nodes.push(node as Text);
    node = walker.nextNode();
  }
  if (!nodes.length) return null;

  const full = nodes.map((t) => t.nodeValue ?? "").join("");
  const range = findQuoteRange(full, needle);
  if (!range) return null;

  let cursor = 0;
  let startNode: Text | null = null;
  let startOffset = 0;
  let endNode: Text | null = null;
  let endOffset = 0;

  for (const textNode of nodes) {
    const len = textNode.nodeValue?.length ?? 0;
    if (!startNode && cursor + len > range.start) {
      startNode = textNode;
      startOffset = range.start - cursor;
    }
    if (!endNode && cursor + len >= range.end) {
      endNode = textNode;
      endOffset = range.end - cursor;
      break;
    }
    cursor += len;
  }

  if (!startNode || !endNode) return null;

  try {
    const domRange = document.createRange();
    domRange.setStart(startNode, startOffset);
    domRange.setEnd(endNode, endOffset);
    const mark = document.createElement("mark");
    mark.className = "cite-highlight";
    domRange.surroundContents(mark);
    return mark;
  } catch {
    try {
      const text = startNode.nodeValue ?? "";
      const before = text.slice(0, startOffset);
      const mid = text.slice(
        startOffset,
        startNode === endNode ? endOffset : text.length,
      );
      const after = startNode === endNode ? text.slice(endOffset) : "";
      const mark = document.createElement("mark");
      mark.className = "cite-highlight";
      mark.textContent = mid;
      const parentEl = startNode.parentNode;
      if (!parentEl) return null;
      if (before) parentEl.insertBefore(document.createTextNode(before), startNode);
      parentEl.insertBefore(mark, startNode);
      if (after) parentEl.insertBefore(document.createTextNode(after), startNode);
      parentEl.removeChild(startNode);
      return mark;
    } catch {
      return null;
    }
  }
}
