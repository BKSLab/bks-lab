import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsSourceForm } from "@/components/admin/news/NewsSourceForm";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { newsSlug } from "@/lib/news-api/params";
import type { NewsSource, NewsTaxonomy } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Настройки источника" };

export default async function NewsSourcePage({ params }: { params: Promise<{ slug: string }> }) {
  const user = await requireAdmin();
  const slug = newsSlug((await params).slug);
  if (!slug) notFound();
  const [source, topics, categories] = await Promise.all([adminFetch<NewsSource>(`/news/sources/${slug}`), adminFetch<NewsTaxonomy[]>("/news/topics"), adminFetch<NewsTaxonomy[]>("/news/categories")]);
  return <NewsShell username={user.username} current="sources" title={source.name} description="Изменение адреса или CSS-селекторов требует повторной проверки. Название, темы и расписание можно сохранить сразу.">
    <div><Link className="admin-link" prefetch={false} href="/admin/news/sources">К источникам</Link></div>
    <section className="admin-section news-stack" aria-labelledby="news-source-collect"><h2 id="news-source-collect">Собрать материалы</h2><NewsJobLauncher sourceSlug={source.slug} /></section>
    <NewsSourceForm key={source.slug} source={source} topics={topics} categories={categories} />
  </NewsShell>;
}
