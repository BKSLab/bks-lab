import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { NewsJobProgress } from "@/components/admin/news/NewsJobProgress";
import { NewsRunReport } from "@/components/admin/news/NewsRunReport";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate, adminHref, adminPage, type AdminSearchParams } from "@/lib/admin-api/params";
import { newsJobTitle, newsRunFilters, newsSlug } from "@/lib/news-api/params";
import type { NewsJob, NewsPaged, NewsRun, NewsRunItem, NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Фоновое задание" };

export default async function NewsJobPage({ params, searchParams }: { params: Promise<{ slug: string }>; searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const slug = newsSlug((await params).slug);
  if (!slug) notFound();
  const job = await adminFetch<NewsJob>(`/news/jobs/${slug}`);
  const query = await searchParams;
  const filters = newsRunFilters(query);
  const page = adminPage(query.page);
  const runsPage = adminPage(query.runs_page);
  const report = job.kind === "collect" ? await Promise.all([
    adminFetch<NewsPaged<NewsRun>>(adminHref(`/news/jobs/${slug}/runs`, { page: runsPage, page_size: 20 })),
    adminFetch<NewsPaged<NewsRunItem>>(adminHref(`/news/jobs/${slug}/items`, { ...filters, page, page_size: 20 })),
    adminFetch<NewsSource[]>("/news/sources"),
  ]) : null;
  return <NewsShell username={user.username} current="runs" title={newsJobTitle(job)} description={job.kind === "collect" ? "Статус и отчёт обновляются во время сбора. Время указано в UTC." : "Статус обновляется автоматически, пока задание выполняется. Время указано в UTC."}>
    <div className="news-actions"><Link className="admin-link" prefetch={false} href="/admin/news/runs">К запускам</Link>{job.source_slug && <Link className="admin-link" prefetch={false} href={`/admin/news/sources/${job.source_slug}`}>Открыть источник</Link>}{job.item_id && <Link className="admin-link" prefetch={false} href={`/admin/news/items/${job.item_id}`}>Открыть материал</Link>}</div>
    <p className="admin-muted">Создано: {adminDate(job.created_at, true)} UTC. Попыток: {job.attempts}.</p>
    {report ? <NewsRunReport key={JSON.stringify([job.slug, filters, page, runsPage])} initialJob={job} initialRuns={report[0]} initialItems={report[1]} sources={report[2]} filters={filters} />
      : <NewsJobProgress key={job.slug} jobSlug={job.slug} initialJob={job} showLink={false} showPreview />}
  </NewsShell>;
}
