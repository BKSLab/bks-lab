"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { AdminPagination } from "@/components/admin/AdminPagination";
import { adminHref } from "@/lib/admin-api/params";
import { newsRequest, NewsRequestError } from "@/lib/news-api/client";
import { sourceDate } from "@/lib/news-api/schedule";
import type { NewsNote, NewsNoteSettings as NoteSettings, NewsNoteStatus, NewsPaged } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";
import { NewsNoteEditDialog } from "./NewsNoteEditDialog";
import { NewsNoteSettings } from "./NewsNoteSettings";

const filters: { status: NewsNoteStatus; label: string; empty: string }[] = [
  { status: "queued", label: "В очереди", empty: "В очереди пока нет заметок." },
  { status: "published", label: "Опубликованы", empty: "Опубликованных заметок пока нет." },
  { status: "excluded", label: "Исключены", empty: "Исключённых заметок нет." },
  { status: "expired", label: "Устарели", empty: "Устаревших заметок нет." },
];

function safeSourceUrl(value: string): string | null {
  try { const url = new URL(value); return url.protocol === "https:" || url.protocol === "http:" ? url.href : null; }
  catch { return null; }
}

export function NewsNotesQueue({ initialSettings, initialQueue, status }: {
  initialSettings: NoteSettings;
  initialQueue: NewsPaged<NewsNote>;
  status: NewsNoteStatus;
}) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const [settings, setSettings] = useState(initialSettings);
  const [queue, setQueue] = useState(initialQueue);
  const [refreshing, setRefreshing] = useState(false);
  const [readError, setReadError] = useState("");
  const [settingsBusy, setSettingsBusy] = useState(false);
  const [editing, setEditing] = useState<NewsNote | null>(null);
  const activeRead = useRef<AbortController | null>(null);
  const editTrigger = useRef<HTMLButtonElement | null>(null);
  const queueHeading = useRef<HTMLHeadingElement>(null);
  const page = initialQueue.page;

  const refreshData = useCallback(async () => {
    activeRead.current?.abort();
    const controller = new AbortController();
    activeRead.current = controller;
    setRefreshing(true);
    setReadError("");
    try {
      const [nextSettings, nextQueue] = await Promise.all([
        newsRequest<NoteSettings>("/note-settings", { signal: controller.signal }),
        newsRequest<NewsPaged<NewsNote>>(adminHref("/note-queue", { status, page, page_size: 20 }), { signal: controller.signal }),
      ]);
      if (controller.signal.aborted || activeRead.current !== controller) return;
      setSettings(nextSettings);
      setQueue(nextQueue);
    } catch (reason) {
      if (controller.signal.aborted || activeRead.current !== controller) return;
      if (reason instanceof NewsRequestError && reason.status === 401) { router.replace("/admin/login"); router.refresh(); }
      setReadError(reason instanceof NewsRequestError ? reason.message : "Не удалось обновить очередь. Попробуйте снова.");
    } finally {
      if (activeRead.current === controller) { activeRead.current = null; setRefreshing(false); }
    }
  }, [status, page, router]);

  function stopRefresh() { activeRead.current?.abort(); activeRead.current = null; setRefreshing(false); }

  useEffect(() => () => { activeRead.current?.abort(); }, []);
  useEffect(() => {
    if (!settings.enabled || editing || settingsBusy || mutation.pending) return;
    const refreshVisible = () => { if (document.visibilityState === "visible" && !activeRead.current) void refreshData(); };
    const timer = setInterval(refreshVisible, 15000);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => { clearInterval(timer); document.removeEventListener("visibilitychange", refreshVisible); };
  }, [settings.enabled, editing, settingsBusy, mutation.pending, refreshData]);

  async function changeStatus(note: NewsNote, nextStatus: "queued" | "excluded") {
    stopRefresh();
    const result = await mutation.run<NewsNote>(`/note-queue/${encodeURIComponent(note.note_slug)}`, { status: nextStatus }, "PATCH");
    if (result) {
      setQueue(current => ({ ...current, items: current.items.filter(item => item.note_slug !== result.note_slug), total: Math.max(0, current.total - 1) }));
      mutation.setMessage(nextStatus === "excluded" ? "Заметка исключена из очереди." : "Заметка возвращена в очередь.");
      queueHeading.current?.focus();
      void refreshData();
    }
  }

  return <div className="news-stack news-notes-workspace">
    <NewsNoteSettings settings={settings} onBusy={busy => { if (busy) stopRefresh(); setSettingsBusy(busy); }} onSaved={result => { setSettings(result); void refreshData(); }} />
    <section className="admin-section" aria-labelledby="news-note-queue-title">
      <div className="news-note-queue-heading"><h2 id="news-note-queue-title" ref={queueHeading} tabIndex={-1}>Очередь заметок</h2><button className="admin-button" type="button" disabled={refreshing || mutation.pending || settingsBusy || Boolean(editing)} onClick={() => void refreshData()}>{refreshing ? "Обновляем…" : "Обновить очередь"}</button></div>
      <nav aria-label="Статусы заметок"><ul className="admin-nav news-note-filters">{filters.map(filter => <li key={filter.status}><Link prefetch={false} href={adminHref("/admin/news/notes", { status: filter.status })} aria-current={status === filter.status ? "page" : undefined}>{filter.label} ({settings[filter.status]})</Link></li>)}</ul></nav>
      <NewsFeedback {...mutation} />
      {readError && <p className="admin-error" role="status">{readError} Нажмите «Обновить очередь», чтобы повторить запрос.</p>}
      <div aria-busy={refreshing}>
        {queue.items.length ? <ul className="news-note-list" aria-label={filters.find(filter => filter.status === status)?.label}>{queue.items.map(note => {
          const sourceUrl = safeSourceUrl(note.source_url);
          return <li key={note.note_slug}><article className="news-note-entry" aria-labelledby={`news-note-heading-${note.note_slug}`}>
            <h3 id={`news-note-heading-${note.note_slug}`}>{note.title}</h3><p className="news-note-text">{note.text}</p>
            <p className="admin-muted news-note-meta">{sourceUrl ? <a className="admin-link" href={sourceUrl} target="_blank" rel="noopener noreferrer">{note.source_name} — первоисточник<span className="sr-only"> (откроется в новой вкладке)</span></a> : <span>{note.source_name}</span>}</p>
            <p className="admin-muted news-note-meta">{note.published_at_time ? <>Опубликована: <time dateTime={note.published_at_time}>{sourceDate(note.published_at_time)}</time>.</> : <>Добавлена: <time dateTime={note.created_at}>{sourceDate(note.created_at)}</time>.</>}</p>
            {note.reason && <p className="admin-muted news-note-meta">{note.reason}</p>}
            <div className="news-actions news-note-actions">
              {(note.status === "queued" || note.status === "excluded") && note.content_id !== null && <button className="admin-button" type="button" disabled={mutation.pending || settingsBusy} onClick={event => { stopRefresh(); editTrigger.current = event.currentTarget; setEditing(note); }} aria-label={`Редактировать заметку: ${note.title}`}>Редактировать</button>}
              {note.status === "queued" && <button className="admin-button" type="button" disabled={mutation.pending || settingsBusy} onClick={() => void changeStatus(note, "excluded")} aria-label={`Исключить заметку: ${note.title}`}>Исключить</button>}
              {note.status === "excluded" && note.content_id !== null && <button className="admin-button" type="button" disabled={mutation.pending || settingsBusy} onClick={() => void changeStatus(note, "queued")} aria-label={`Вернуть в очередь: ${note.title}`}>Вернуть в очередь</button>}
              {note.status === "published" && note.content_id !== null && <Link className="admin-button" prefetch={false} href={`/admin/content/${note.content_id}/edit`}>Открыть в редакторе</Link>}
            </div>
          </article></li>;
        })}</ul> : <div className="admin-empty"><p>{queue.total ? "На этой странице нет заметок. Вернитесь на первую страницу." : filters.find(filter => filter.status === status)?.empty}</p></div>}
      </div>
      <AdminPagination path="/admin/news/notes" page={queue.page} pages={queue.pages ?? Math.ceil(queue.total / queue.page_size)} total={queue.total} params={{ status }} label="Страницы заметок" />
    </section>
    {editing && <NewsNoteEditDialog note={editing} restoreFocus={editTrigger} onClose={() => setEditing(null)} onSaved={result => {
      setQueue(current => ({ ...current, items: current.items.map(note => note.note_slug === result.note_slug ? result : note) }));
      setEditing(null);
      mutation.setMessage("Заметка сохранена.");
      void refreshData();
    }} />}
  </div>;
}
