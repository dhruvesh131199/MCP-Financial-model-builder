import { useMemo, useState } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  isCitationHref,
  parseCitationHref,
  rewriteCiteMarkersToLinks,
} from "../lib/citeMarkers";
import CitationSourceDrawer from "./CitationSourceDrawer";

export interface MarkdownWithCitationsProps {
  markdown: string;
  sessionId: string;
  className?: string;
}

interface OpenCite {
  parentId: string;
  quote?: string;
}

const CHIP_MAX = 36;

function citationChipLabel(quote?: string): string {
  const t = quote?.trim();
  if (!t) return "source";
  if (t.length <= CHIP_MAX) return t;
  return `${t.slice(0, CHIP_MAX - 1)}…`;
}

/**
 * Renders GFM markdown with [[cite:parent_id]] chips that open the source drawer.
 */
export default function MarkdownWithCitations({
  markdown,
  sessionId,
  className,
}: MarkdownWithCitationsProps) {
  const [open, setOpen] = useState<OpenCite | null>(null);

  const rewritten = useMemo(() => rewriteCiteMarkersToLinks(markdown), [markdown]);

  const components = useMemo<Components>(
    () => ({
      a: ({ href, children, ...rest }) => {
        if (isCitationHref(href)) {
          const cite = parseCitationHref(href ?? "");
          if (!cite) return <span>{children}</span>;
          const label = citationChipLabel(cite.quote);
          const hasQuote = Boolean(cite.quote?.trim());
          return (
            <button
              type="button"
              className="mx-0.5 inline cursor-pointer rounded-sm bg-gray-100/90 px-1 py-px align-baseline text-[10.5px] font-medium leading-snug text-gray-600 shadow-[inset_0_0_0_1px_rgba(0,0,0,0.06)] transition-colors hover:bg-gray-200/90 hover:text-gray-800 hover:shadow-[inset_0_0_0_1px_rgba(0,0,0,0.1)]"
              title={cite.quote?.trim() || `Open source ${cite.parentId}`}
              aria-label={hasQuote ? `Source: ${label}` : "Open source"}
              onClick={(e) => {
                e.preventDefault();
                setOpen({ parentId: cite.parentId, quote: cite.quote });
              }}
            >
              {hasQuote ? (
                <span className="italic">“{label}”</span>
              ) : (
                <span>source</span>
              )}
            </button>
          );
        }
        return (
          <a href={href} {...rest}>
            {children}
          </a>
        );
      },
    }),
    [],
  );

  return (
    <>
      <div className={className}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {rewritten}
        </ReactMarkdown>
      </div>
      {open ? (
        <CitationSourceDrawer
          sessionId={sessionId}
          parentId={open.parentId}
          quote={open.quote}
          onClose={() => setOpen(null)}
        />
      ) : null}
    </>
  );
}
