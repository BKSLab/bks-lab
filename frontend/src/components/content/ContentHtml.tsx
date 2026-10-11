import { Fragment, type ReactNode } from "react";

import { AdSlot } from "@/components/ads/AdSlot";
import { sanitizeContent } from "@/lib/sanitize";

/** Exact fragment the backend emits for a standalone `::ad` marker line in article bodies. */
const AD_SLOT_FRAGMENT = '<div data-ad-slot="article-inline"></div>';

const defaultRenderAdSlot = (index: number) => <AdSlot key={index} placement="article-inline" height={250} />;

export function ContentHtml({ html, renderAdSlot }: { html: string; renderAdSlot?: (index: number) => ReactNode }) {
  const parts = html.split(AD_SLOT_FRAGMENT);
  if (parts.length === 1) {
    return (
      <div
        className="prose-content"
        dangerouslySetInnerHTML={{ __html: sanitizeContent(html) }}
      />
    );
  }
  const renderSlot = renderAdSlot ?? defaultRenderAdSlot;
  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>
          {part.trim() ? (
            <div
              className="prose-content"
              dangerouslySetInnerHTML={{ __html: sanitizeContent(part) }}
            />
          ) : null}
          {index < parts.length - 1 ? renderSlot(index) : null}
        </Fragment>
      ))}
    </>
  );
}
