import type { Metadata } from "next";
import { NewsNotesQueue } from "@/components/admin/news/NewsNotesQueue";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminHref, adminPage, firstParam, type AdminSearchParams } from "@/lib/admin-api/params";
import type { NewsNote, NewsNoteSettings, NewsNoteStatus, NewsPaged } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Заметки редакционного центра" };

export default async function NewsNotesPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const requestedStatus = firstParam(params.status);
  const status: NewsNoteStatus = requestedStatus === "published" || requestedStatus === "excluded" || requestedStatus === "expired" ? requestedStatus : "queued";
  const page = adminPage(params.page);
  const [settings, queue] = await Promise.all([
    adminFetch<NewsNoteSettings>("/news/note-settings"),
    adminFetch<NewsPaged<NewsNote>>(adminHref("/news/note-queue", { status, page, page_size: 20 })),
  ]);

  return <NewsShell username={user.username} current="notes" title="Заметки" description="Короткие заметки из найденных новостей. Проверьте очередь и настройте автоматическую публикацию. Время указано по Самаре (UTC+4).">
    <NewsNotesQueue key={`${status}:${page}`} initialSettings={settings} initialQueue={queue} status={status} />
  </NewsShell>;
}
