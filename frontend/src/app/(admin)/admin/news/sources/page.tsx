import type { Metadata } from "next";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsCollectionWorkspace } from "@/components/admin/news/NewsCollectionWorkspace";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import type { NewsCollectionStatus, NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Источники редакционного центра" };

export default async function NewsSourcesPage() {
  const user = await requireAdmin();
  const [sources, status] = await Promise.all([adminFetch<NewsSource[]>("/news/sources"), adminFetch<NewsCollectionStatus>("/news/collection-status")]);
  return <NewsShell username={user.username} current="sources" title="Источники публикаций" description="Включите нужные источники и выберите расписание проверок. Всё время указано по Самаре (UTC+4).">
    <NewsCollectionWorkspace initialSources={sources} initialStatus={status} />
  </NewsShell>;
}
