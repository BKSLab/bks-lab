"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";

import { fetchNotesFeed } from "@/lib/api/notes-feed";
import type { Note, NotesFeedPage } from "@/lib/api/types";
import { NoteAnchorFocus } from "./NoteAnchorFocus";
import { NoteEntry } from "./NoteEntry";

const POLL_INTERVAL_MS = 60_000;
const MAX_AUTOMATIC_LOADS = 2;

function uniqueNotes(notes: Note[]) {
  const seen = new Set<string>();
  return notes.filter((note) => {
    if (seen.has(note.slug)) return false;
    seen.add(note.slug);
    return true;
  });
}

export function NotesFeed({
  initialFeed,
  compact = false,
  pageSize = 20,
}: {
  initialFeed: NotesFeedPage;
  compact?: boolean;
  pageSize?: number;
}) {
  const [feed, setFeed] = useState(() => ({
    ...initialFeed,
    items: uniqueNotes(initialFeed.items),
  }));
  const [loadingMore, setLoadingMore] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [hasNew, setHasNew] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [automaticLoads, setAutomaticLoads] = useState(0);
  const [automaticPaused, setAutomaticPaused] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const moreController = useRef<AbortController | null>(null);
  const pollController = useRef<AbortController | null>(null);
  const refreshController = useRef<AbortController | null>(null);
  const focusAfterUpdate = useRef<string | null>(null);
  const listId = useId();

  useEffect(() => {
    if (focusAfterUpdate.current === null) return;
    const slug = focusAfterUpdate.current;
    focusAfterUpdate.current = null;
    const target = slug ? document.getElementById(`note-${slug}`) : scrollRef.current;
    target?.focus({ preventScroll: true });
    target?.scrollIntoView?.({ block: "nearest" });
  }, [feed.items]);

  const loadMore = useCallback(async (automatic = false) => {
    if (!feed.has_more || !feed.next_cursor || moreController.current || refreshController.current) return;
    const controller = new AbortController();
    moreController.current = controller;
    setLoadingMore(true);
    setError(null);
    try {
      const page = await fetchNotesFeed({ limit: pageSize, before: feed.next_cursor }, controller.signal);
      if (controller.signal.aborted) return;
      const existing = new Set(feed.items.map((note) => note.slug));
      const added = uniqueNotes(page.items).filter((note) => !existing.has(note.slug));
      if (!automatic) focusAfterUpdate.current = added[0]?.slug ?? "";
      if (automatic) setAutomaticLoads((count) => count + 1);
      setFeed((current) => ({
        ...current,
        items: uniqueNotes([...current.items, ...page.items]),
        next_cursor: page.next_cursor,
        has_more: page.has_more,
      }));
      setStatus(added.length ? "Добавлены заметки." : "Других заметок пока нет.");
    } catch {
      if (!controller.signal.aborted) {
        setError("Не удалось загрузить заметки. Попробуйте ещё раз.");
        setAutomaticPaused(true);
      }
    } finally {
      if (moreController.current === controller) {
        moreController.current = null;
        if (!controller.signal.aborted) setLoadingMore(false);
      }
    }
  }, [feed.has_more, feed.next_cursor, feed.items, pageSize]);

  const refresh = useCallback(async () => {
    if (refreshController.current) return;
    moreController.current?.abort();
    moreController.current = null;
    pollController.current?.abort();
    pollController.current = null;
    const controller = new AbortController();
    refreshController.current = controller;
    setLoadingMore(false);
    setRefreshing(true);
    setError(null);
    try {
      const page = await fetchNotesFeed({ limit: pageSize }, controller.signal);
      if (controller.signal.aborted) return;
      focusAfterUpdate.current = page.items[0]?.slug ?? "";
      setFeed({ ...page, items: uniqueNotes(page.items) });
      setHasNew(false);
      setAutomaticLoads(0);
      setAutomaticPaused(false);
      setStatus("Лента обновлена.");
    } catch {
      if (!controller.signal.aborted) setError("Не удалось обновить заметки. Попробуйте ещё раз.");
    } finally {
      if (refreshController.current === controller) {
        refreshController.current = null;
        if (!controller.signal.aborted) setRefreshing(false);
      }
    }
  }, [pageSize]);

  const checkNew = useCallback(async () => {
    if (document.visibilityState !== "visible" || hasNew || pollController.current || refreshController.current) return;
    const controller = new AbortController();
    pollController.current = controller;
    try {
      const page = await fetchNotesFeed(
        feed.newest_cursor ? { limit: 1, after: feed.newest_cursor } : { limit: 1 },
        controller.signal,
      );
      if (!controller.signal.aborted && page.items.some((note) => !feed.items.some((item) => item.slug === note.slug))) {
        setHasNew(true);
        setStatus("Появились новые заметки. Их можно показать кнопкой над лентой.");
      }
    } catch {
      // Polling is optional: retain readable content and try at the next interval.
    } finally {
      if (pollController.current === controller) pollController.current = null;
    }
  }, [feed.newest_cursor, feed.items, hasNew]);

  useEffect(() => {
    const timer = window.setInterval(() => void checkNew(), POLL_INTERVAL_MS);
    const visible = () => {
      if (document.visibilityState === "visible") void checkNew();
      else pollController.current?.abort();
    };
    document.addEventListener("visibilitychange", visible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", visible);
      pollController.current?.abort();
      pollController.current = null;
    };
  }, [checkNew]);

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !feed.has_more || !feed.next_cursor || loadingMore || refreshing || automaticPaused || automaticLoads >= MAX_AUTOMATIC_LOADS || typeof IntersectionObserver === "undefined") return;
    let active = true;
    const observer = new IntersectionObserver((entries) => {
      if (active && entries.some((entry) => entry.isIntersecting) && document.visibilityState === "visible") {
        void loadMore(true);
      }
    }, { root: compact ? scrollRef.current : null, rootMargin: "120px 0px" });
    observer.observe(sentinel);
    return () => {
      active = false;
      observer.disconnect();
    };
  }, [compact, feed.has_more, feed.next_cursor, loadingMore, refreshing, automaticPaused, automaticLoads, loadMore]);

  useEffect(() => () => {
    moreController.current?.abort();
    pollController.current?.abort();
    refreshController.current?.abort();
  }, []);

  return (
    <div className={`notes-feed${compact ? " notes-feed-compact" : ""}`}>
      {(hasNew || refreshing) && (
        <div className="notes-feed-notice">
          <button type="button" className="button-secondary" onClick={() => void refresh()} disabled={refreshing} aria-controls={listId}>
            {refreshing ? "Обновляем…" : "Появились новые"}
          </button>
        </div>
      )}
      <div
        ref={scrollRef}
        className={compact ? "notes-feed-scroll" : undefined}
        role={compact ? "region" : undefined}
        aria-label={compact ? "Лента заметок" : undefined}
        tabIndex={compact ? 0 : -1}
        aria-busy={loadingMore || refreshing}
      >
        <div id={listId}>
          {feed.items.map((note) => <NoteEntry key={note.slug} note={note} compact={compact} />)}
        </div>
        {!feed.items.length && <p className="notes-feed-empty">Заметки скоро появятся.</p>}
        <div ref={sentinelRef} aria-hidden="true" />
        {feed.has_more && feed.next_cursor && (
          <div className="notes-feed-controls">
            <button
              type="button"
              className="button-secondary"
              onClick={() => void loadMore()}
              disabled={loadingMore || refreshing}
              aria-controls={listId}
            >
              {loadingMore ? "Загружаем…" : error && !hasNew ? "Повторить загрузку" : "Ещё заметки"}
            </button>
          </div>
        )}
      </div>
      {error && <p role="alert" className="notes-feed-error">{error}</p>}
      <p role="status" className="sr-only">{status}</p>
      <NoteAnchorFocus />
    </div>
  );
}
