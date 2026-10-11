"use client";

import { useEffect, useRef, useState } from "react";

import { ContentHtml } from "@/components/content/ContentHtml";
import { renderMarkdownPreview } from "@/lib/admin-api/content-client";

const PREVIEW_DEBOUNCE_MS = 400;

/** Live preview: debounced Markdown render through the same sanitize pipeline as the public site. */
export function EditorPreview({ markdown }: { markdown: string }) {
  const [html, setHtml] = useState("");
  const [busy, setBusy] = useState(false);
  const requestRef = useRef(0);

  useEffect(() => {
    if (!markdown.trim()) {
      requestRef.current += 1;
      return;
    }
    const requestId = ++requestRef.current;
    const timeout = setTimeout(() => {
      setBusy(true);
      renderMarkdownPreview(markdown)
        .then((result) => {
          if (requestRef.current !== requestId) return;
          setHtml(result.html);
          setBusy(false);
        })
        .catch(() => {
          if (requestRef.current !== requestId) return;
          setBusy(false);
        });
    }, PREVIEW_DEBOUNCE_MS);
    return () => clearTimeout(timeout);
  }, [markdown]);

  const shownHtml = markdown.trim() ? html : "";

  return (
    <section className="editor-preview" aria-label="Предпросмотр материала" aria-busy={busy}>
      <h2 className="editor-preview-heading">Предпросмотр</h2>
      {busy && <p className="admin-muted" role="status">Обновляем предпросмотр…</p>}
      {shownHtml ? (
        <ContentHtml
          html={shownHtml}
          renderAdSlot={(index) => (
            <div key={index} className="editor-ad-placeholder" aria-hidden="true">Рекламный блок</div>
          )}
        />
      ) : !busy && <p className="admin-muted">Начните вводить текст, чтобы увидеть, как материал будет выглядеть на сайте.</p>}
    </section>
  );
}
