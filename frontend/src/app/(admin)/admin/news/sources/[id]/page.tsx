import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsSourceForm } from "@/components/admin/news/NewsSourceForm";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { newsId } from "@/lib/news-api/params";
import type { NewsSource, NewsTaxonomy } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Настройки источника" };

export default async function NewsSourcePage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireAdmin();
  const id = newsId((await params).id);
  if (!id) notFound();
  const [sources, topics, categories] = await Promise.all([adminFetch<NewsSource[]>("/news/sources"), adminFetch<NewsTaxonomy[]>("/news/topics"), adminFetch<NewsTaxonomy[]>("/news/categories")]);
  const source = sources.find(value => value.id === Number(id));
  if (!source) notFound();
  return <NewsShell username={user.username} current="sources" title={source.name} description="Изменение адреса или CSS-селекторов требует повторной проверки. Название, темы и расписание можно сохранить сразу.">
    <div><Link className="admin-link" prefetch={false} href="/admin/news/sources">К источникам</Link></div>
    <section className="admin-section news-stack" aria-labelledby="news-source-collect"><h2 id="news-source-collect">Собрать материалы</h2><NewsJobLauncher sourceId={source.id} /></section>
    <NewsSourceForm key={source.id} source={source} topics={topics} categories={categories} />
  </NewsShell>;
}
