import { sanitizeContent } from "@/lib/sanitize";

export function ContentHtml({ html }: { html: string }) {
  return (
    <div
      className="prose-content"
      dangerouslySetInnerHTML={{ __html: sanitizeContent(html) }}
    />
  );
}
