"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { contentRequest, ContentRequestError, renderMarkdownPreview } from "@/lib/admin-api/content-client";
import { adminDate, adminNumber } from "@/lib/admin-api/params";
import type { AdminContentDetail, ContentRevisionInfo, ContentRevisionSnapshot } from "@/lib/admin-api/types";
import { ContentHtml } from "@/components/content/ContentHtml";
import { ConfirmDialog } from "./ConfirmDialog";

export function RevisionList({ itemId, onRestored }: { itemId: number; onRestored?: (item: AdminContentDetail) => void }) {
  const router = useRouter();
  const [revisions, setRevisions] = useState<ContentRevisionInfo[] | null>(null);
  const [error, setError] = useState("");
  const [viewing, setViewing] = useState<{ info: ContentRevisionSnapshot; html: string } | null>(null);
  const [viewBusy, setViewBusy] = useState(false);
  const [restoring, setRestoring] = useState<ContentRevisionInfo | null>(null);
  const [restoreBusy, setRestoreBusy] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    let cancelled = false;
    contentRequest<ContentRevisionInfo[]>(`/${itemId}/revisions`)
      .then((rows) => { if (!cancelled) setRevisions(rows); })
      .catch((reason) => {
        if (cancelled) return;
        setError(reason instanceof ContentRequestError ? reason.message : "Не удалось загрузить список версий.");
      });
    return () => { cancelled = true; };
  }, [itemId]);

  async function view(revision: ContentRevisionInfo) {
    setError("");
    setMessage("");
    setViewBusy(true);
    try {
      const snapshot = await contentRequest<ContentRevisionSnapshot>(`/${itemId}/revisions/${revision.revision_no}`);
      const rendered = await renderMarkdownPreview(snapshot.snapshot.content_markdown ?? "");
      setViewing({ info: snapshot, html: rendered.html });
    } catch (reason) {
      setError(reason instanceof ContentRequestError ? reason.message : "Не удалось загрузить снимок версии.");
    } finally {
      setViewBusy(false);
    }
  }

  async function restore() {
    if (!restoring) return;
    setRestoreBusy(true);
    setError("");
    try {
      const item = await contentRequest<AdminContentDetail>(`/${itemId}/revisions/${restoring.revision_no}/restore`, { method: "POST" });
      setMessage(`Версия ${restoring.revision_no} восстановлена как текущая.`);
      setRestoring(null);
      setViewing(null);
      onRestored?.(item);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof ContentRequestError ? reason.message : "Не удалось восстановить версию.");
    } finally {
      setRestoreBusy(false);
    }
  }

  if (revisions === null && !error) {
    return <p className="admin-muted" role="status">Загружаем список версий…</p>;
  }

  return (
    <section className="editor-revisions" aria-label="История версий">
      {error && <p className="admin-error" role="alert">{error}</p>}
      {message && <p className="admin-muted" role="status">{message}</p>}
      {revisions && (revisions.length ? (
        <ul className="editor-revision-list">
          {revisions.map((revision) => (
            <li className="editor-revision" key={revision.revision_no}>
              <div className="editor-revision-meta">
                <span className="editor-revision-title">Версия {adminNumber(revision.revision_no)}</span>
                <span className="admin-muted"><time dateTime={revision.created_at}>{adminDate(revision.created_at, true)}, UTC</time> · слов: {adminNumber(revision.word_count)}</span>
              </div>
              <div className="editor-revision-actions">
                <button type="button" className="admin-button" onClick={() => view(revision)} disabled={viewBusy}>
                  {viewBusy && viewing?.info.revision_no === revision.revision_no ? "Открываем…" : "Просмотреть"}
                </button>
                <button type="button" className="admin-button" onClick={() => { setRestoring(revision); setMessage(""); }} disabled={restoreBusy}>
                  Откатить
                </button>
              </div>
            </li>
          ))}
        </ul>
      ) : (
        <p className="admin-empty">У материала пока нет сохранённых версий. Версия появится после первого сохранения.</p>
      ))}
      {viewing && (
        <section className="editor-revision-snapshot" aria-label={`Снимок версии ${viewing.info.revision_no}`}>
          <h3>Снимок версии {adminNumber(viewing.info.revision_no)}</h3>
          <p className="admin-muted">Заголовок: {viewing.info.snapshot.title}. Слов: {adminNumber(viewing.info.word_count)}.</p>
          <div className="editor-revision-html"><ContentHtml html={viewing.html} /></div>
        </section>
      )}
      <ConfirmDialog
        open={restoring !== null}
        title="Откатить версию"
        description={restoring ? `Текущее состояние материала будет заменено содержимым версии ${adminNumber(restoring.revision_no)}. История версий сохранится.` : ""}
        confirmLabel="Откатить"
        pending={restoreBusy}
        onConfirm={restore}
        onCancel={() => setRestoring(null)}
      />
    </section>
  );
}
