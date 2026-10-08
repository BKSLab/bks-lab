import type { Metadata } from "next";
import Link from "next/link";
import { AdminPagination } from "@/components/admin/AdminPagination";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate, adminHref, adminPage, type AdminSearchParams } from "@/lib/admin-api/params";
import { jobStatusLabels } from "@/lib/news-api/params";
import type { NewsPaged, NewsRun, NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Запуски сбора" };

export default async function NewsRunsPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const page = adminPage((await searchParams).page);
  const [data, sources] = await Promise.all([adminFetch<NewsPaged<NewsRun>>(adminHref("/news/runs", { page, page_size: 20 })), adminFetch<NewsSource[]>("/news/sources")]);
  return <NewsShell username={user.username} current="runs" title="Запуски и история" description="Ручной сбор выполняется в фоне. После создания задания можно закрыть страницу и вернуться по его ссылке.">
    <section className="admin-section news-stack" aria-labelledby="news-run-heading"><h2 id="news-run-heading">Запустить сбор</h2>{sources.length ? <NewsJobLauncher sources={sources} /> : <p className="admin-empty">Сначала <Link className="admin-link" prefetch={false} href="/admin/news/sources/new">добавьте источник</Link>.</p>}</section>
    <section className="admin-section" aria-labelledby="news-runs-heading"><h2 id="news-runs-heading">История обходов</h2>
      {data.items.length ? <table className="admin-table admin-card-table" role="table"><caption>Время — UTC. Новые и изменённые материалы сохраняются до анализа моделью.</caption>
        <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Источник / начало</th><th scope="col" role="columnheader">Состояние</th><th scope="col" role="columnheader">Материалы</th><th scope="col" role="columnheader">Задание</th></tr></thead>
        <tbody role="rowgroup">{data.items.map(run => <tr role="row" key={run.id}>
          <th scope="row" role="rowheader"><Link href={`/admin/news/sources/${run.source_id}`} prefetch={false}>{run.source_name}</Link><span className="admin-type">{adminDate(run.started_at, true)}</span></th>
          <td role="cell" data-label="Состояние"><span className="admin-status">{jobStatusLabels[run.status]}</span>{run.error && <p className="admin-error">{run.error}</p>}</td>
          <td role="cell" data-label="Материалы">Новых: {run.new_count}<small>Обновлено: {run.updated_count}; без изменений: {run.unchanged_count}</small></td>
          <td role="cell" data-label="Задание">{run.job_id ? <Link prefetch={false} href={`/admin/news/jobs/${run.job_id}`}>№ {run.job_id}</Link> : "Недоступно"}</td>
        </tr>)}</tbody>
      </table> : <p className="admin-empty">Обходов ещё не было. Запустите сбор вручную или включите расписание в настройках.</p>}
      <AdminPagination path="/admin/news/runs" page={data.page} total={data.total} pages={data.pages ?? Math.ceil(data.total / data.page_size)} />
    </section>
  </NewsShell>;
}
