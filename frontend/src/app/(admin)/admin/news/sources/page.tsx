import type { Metadata } from "next";
import Link from "next/link";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { NewsSourcesList } from "@/components/admin/news/NewsSourcesList";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import type { NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Источники редакционного центра" };

export default async function NewsSourcesPage() {
  const user = await requireAdmin();
  const sources = await adminFetch<NewsSource[]>("/news/sources");
  return <NewsShell username={user.username} current="sources" title="Источники публикаций" description="Включите нужные источники и выберите расписание проверок. Всё время указано по Самаре (UTC+4).">
    <div className="news-actions">{sources.length > 0 && <NewsJobLauncher allActive />}<Link className="admin-link" prefetch={false} href="/admin/news/runs">История проверок</Link></div>
    <NewsSourcesList sources={sources} />
  </NewsShell>;
}
