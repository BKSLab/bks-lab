import DOMPurify from "isomorphic-dompurify";

// Only publication markup is allowed; forms, embedded documents and active
// content cannot enter a public page through Markdown or API responses.
export function sanitizeContent(html: string) {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: [
      "p",
      "br",
      "hr",
      "h2",
      "h3",
      "h4",
      "h5",
      "h6",
      "a",
      "strong",
      "em",
      "del",
      "s",
      "blockquote",
      "ul",
      "ol",
      "li",
      "pre",
      "code",
      "table",
      "thead",
      "tbody",
      "tr",
      "th",
      "td",
      "img",
      "figure",
      "figcaption",
      "sup",
      "sub",
    ],
    ALLOWED_ATTR: [
      "href",
      "src",
      "alt",
      "title",
      "width",
      "height",
      "start",
      "scope",
      "colspan",
      "rowspan",
    ],
    ALLOW_DATA_ATTR: false,
    ALLOW_ARIA_ATTR: false,
  });
}
