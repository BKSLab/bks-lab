import type { NewsNote, NewsNoteSettings, NewsPaged } from "@/lib/news-api/types";

export const noteSettings: NewsNoteSettings = {
  enabled: false,
  interval_minutes: 60,
  max_age_hours: 72,
  started_at: "2026-10-15T08:00:00Z",
  last_published_at: null,
  next_publish_at: null,
  queued: 1,
  published: 0,
  excluded: 0,
  expired: 0,
};

export const queuedNote: NewsNote = {
  note_slug: "note-automatic-a1b2",
  content_id: 982,
  title: "Новый инструмент для разработчиков",
  text: "Вышел инструмент для проверки доступности интерфейсов. Он помогает найти проблемы до публикации.",
  source_name: "Новости разработки",
  source_url: "https://example.org/news/accessibility",
  status: "queued",
  created_at: "2026-10-15T11:00:00Z",
  published_at_time: null,
  reason: null,
};

export function notePage(items: NewsNote[] = [queuedNote]): NewsPaged<NewsNote> {
  return { items, total: items.length, page: 1, page_size: 20, pages: items.length ? 1 : 0 };
}
