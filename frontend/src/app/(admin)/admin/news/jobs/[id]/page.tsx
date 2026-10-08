import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { NewsJobProgress } from "@/components/admin/news/NewsJobProgress";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate } from "@/lib/admin-api/params";
import { newsId } from "@/lib/news-api/params";
import type { NewsJob } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Фоновое задание" };

export default async function NewsJobPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireAdmin();
  const id = newsId((await params).id);
  if (!id) notFound();
  const job = await adminFetch<NewsJob>(`/news/jobs/${id}`);
  return <NewsShell username={user.username} current="runs" title={`Задание № ${job.id}`} description="Статус обновляется автоматически, пока задание находится в очереди или выполняется.">
    <div className="news-actions"><Link className="admin-link" prefetch={false} href="/admin/news/runs">К запускам</Link>{job.source_id && <Link className="admin-link" prefetch={false} href={`/admin/news/sources/${job.source_id}`}>Открыть источник</Link>}{job.item_id && <Link className="admin-link" prefetch={false} href={`/admin/news/items/${job.item_id}`}>Открыть материал</Link>}</div>
    <p className="admin-muted">Создано: {adminDate(job.created_at, true)} UTC. Попыток: {job.attempts}.</p>
    <NewsJobProgress key={job.id} jobId={job.id} initialJob={job} showLink={false} showPreview />
  </NewsShell>;
}
