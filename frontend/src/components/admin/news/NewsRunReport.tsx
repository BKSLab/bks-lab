"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AdminPagination } from "@/components/admin/AdminPagination";
import { adminDate, adminHref } from "@/lib/admin-api/params";
import { newsRequest, NewsRequestError } from "@/lib/news-api/client";
import { externalNewsUrl, jobStatusLabels, newsDuration, runOutcomeLabels } from "@/lib/news-api/params";
import type { NewsJob, NewsPaged, NewsRun, NewsRunItem, NewsSource } from "@/lib/news-api/types";
import { NewsFeedback } from "./NewsFeedback";
import { NewsJobProgress } from "./NewsJobProgress";

const active = (status: string | null) => status === "queued" || status === "running";
const stages: Record<string, string> = { parsing: "Разбор публикации", filter: "Фильтрация", fetch: "Загрузка страницы", extraction: "Извлечение текста", storage: "Сохранение" };
const analysisLabels: Record<string, string> = {
  pending: "Ожидает постановки в очередь", queued: "В очереди на анализ", running: "Анализируется",
  completed: "Анализ готов", failed: "Ошибка анализа", cancelled: "Анализ отменён", skipped: "Анализ пропущен",
};

function RunTimes({ started, completed }: { started: string | null; completed: string | null }) {
  return <dl className="news-job-counts">
    <div><dt>Начало (UTC)</dt><dd>{started ? adminDate(started, true) : "Ещё не начато"}</dd></div>
    <div><dt>Окончание (UTC)</dt><dd>{completed ? adminDate(completed, true) : "Ещё не завершено"}</dd></div>
    <div><dt>Длительность</dt><dd>{newsDuration(started, completed)}</dd></div>
  </dl>;
}

function RunParameters({ parameters }: { parameters: NewsRun["parameters"] }) {
  const number = (key: string, label: string) => typeof parameters[key] === "number" && <div key={key}><dt>{label}</dt><dd>{String(parameters[key])}</dd></div>;
  return <dl className="news-run-parameters">
    {typeof parameters.cutoff === "string" && <div><dt>Публикации начиная с (UTC)</dt><dd>{adminDate(parameters.cutoff, true)}</dd></div>}
    {number("initial_lookback_days", "Глубина первого сбора, дней")}
    {number("max_items_per_source", "Лимит материалов")}
    {number("max_excerpt_chars", "Лимит текста, символов")}
    {typeof parameters.first_run === "boolean" && <div><dt>Обход</dt><dd>{parameters.first_run ? "Первый" : "Повторный"}</dd></div>}
    {typeof parameters.conditional_request === "boolean" && <div><dt>Условный HTTP-запрос</dt><dd>{parameters.conditional_request ? "Да" : "Нет"}</dd></div>}
    {["collect", "repair"].includes(String(parameters.mode)) && <div><dt>Режим</dt><dd>{parameters.mode === "repair" ? "Восстановление текста" : "Сбор публикаций"}</dd></div>}
    {["manual", "scheduled"].includes(String(parameters.trigger)) && <div><dt>Запуск</dt><dd>{parameters.trigger === "scheduled" ? "По расписанию" : "Вручную"}</dd></div>}
  </dl>;
}

function SourceRun({ run }: { run: NewsRun }) {
  const url = externalNewsUrl(run.source_url);
  return <article className="news-stack news-source-run" aria-labelledby={`news-run-${run.id}`}>
    <header className="news-stack">
      <h3 id={`news-run-${run.id}`}><a className="admin-link" href={`/admin/news/sources#${run.source_slug}`}>{run.source_name}</a></h3>
      <p className="news-badges"><span className="admin-status">{jobStatusLabels[run.status]}</span><span>{run.source_kind === "rss" ? "RSS / Atom" : "HTML"}</span>{run.http_status !== null && <span>HTTP {run.http_status}</span>}</p>
      {url && <a className="admin-link news-source-url" href={url} target="_blank" rel="noopener noreferrer">{run.source_url}<span className="sr-only"> (в новой вкладке)</span></a>}
    </header>
    <RunTimes started={run.started_at} completed={run.completed_at} />
    <dl className="news-job-counts">
      {([["Новых", run.new_count], ["Обновлено", run.updated_count], ["Без изменений", run.unchanged_count], ["Пропущено", run.skipped_count], ["Предупреждений", run.warning_count]] as const).map(([label, count]) => <div key={label}><dt>{label}</dt><dd>{count}</dd></div>)}
    </dl>
    {run.not_modified && <p>Источник ответил «Без изменений» (HTTP 304). Список публикаций повторно не передавался.</p>}
    {run.error && <p className="admin-error">{run.error}</p>}
    {run.limit_reached && <p className="admin-muted">Достигнут лимит материалов этого обхода. Остальные публикации не проверялись.</p>}
    {run.diagnostics_truncated && <p className="admin-muted">Достигнут лимит подробного отчёта. Часть диагностических записей не сохранена; число пропусков может быть неполным.</p>}
    <details className="news-run-details"><summary>Параметры обхода</summary><RunParameters parameters={run.parameters} /></details>
  </article>;
}

function RunItem({ item }: { item: NewsRunItem }) {
  const url = item.url ? externalNewsUrl(item.url) : undefined;
  return <article className="news-stack news-observation" aria-labelledby={`news-observation-${item.id}`}>
    <header className="news-stack">
      <h3 id={`news-observation-${item.id}`}>{item.item_id ? <Link className="admin-link" prefetch={false} href={`/admin/news/items/${item.item_id}`}>{item.title || "Публикация без заголовка"}</Link> : item.title || "Публикация без заголовка"}</h3>
      <p className="news-item-meta"><a className="admin-link" href={`/admin/news/sources#${item.source_slug}`}>{item.source_name}</a></p>
      <p className="news-badges"><span className="admin-status">{runOutcomeLabels[item.outcome]}</span>{item.stage && <span>Этап: {stages[item.stage] ?? "Обработка публикации"}</span>}</p>
      {url && <a className="admin-link news-original" href={url} target="_blank" rel="noopener noreferrer">Первоисточник<span className="sr-only">: {item.title} (в новой вкладке)</span></a>}
    </header>
    {item.reason && <p>{item.reason}</p>}
    {item.warning && <p className="admin-error">Предупреждение: {item.warning}</p>}
    {item.preserved_previous && <p>Сохранена предыдущая версия материала.</p>}
    <p>Анализ: {item.analysis_status ? analysisLabels[item.analysis_status] : "Не выполнялся для этой записи"}.</p>
    {item.analysis_reason && <p>{item.analysis_reason}</p>}
    {item.analysis_job_slug && <div><Link className="admin-link" prefetch={false} href={`/admin/news/jobs/${item.analysis_job_slug}`}>Открыть задание анализа<span className="sr-only">: {item.title}</span></Link></div>}
  </article>;
}

export function NewsRunReport({ initialJob, initialRuns, initialItems, sources, filters }: {
  initialJob: NewsJob; initialRuns: NewsPaged<NewsRun>; initialItems: NewsPaged<NewsRunItem>;
  sources: NewsSource[]; filters: Record<string, string>;
}) {
  const router = useRouter();
  const [job, setJob] = useState(initialJob);
  const [runs, setRuns] = useState(initialRuns);
  const [items, setItems] = useState(initialItems);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const runsPath = adminHref(`/jobs/${initialJob.slug}/runs`, { page: initialRuns.page, page_size: initialRuns.page_size });
  const itemsPath = adminHref(`/jobs/${initialJob.slug}/items`, { ...filters, page: initialItems.page, page_size: initialItems.page_size });

  useEffect(() => {
    const runningSource = initialJob.status === "completed" && initialRuns.items.some(run => run.status === "running");
    if (attempt === 0 && !active(initialJob.status) && !runningSource && !initialItems.items.some(item => active(item.analysis_status))) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function refresh() {
      try {
        const [nextJob, nextRuns, nextItems] = await Promise.all([
          newsRequest<NewsJob>(`/jobs/${initialJob.slug}`, { signal: controller.signal }),
          newsRequest<NewsPaged<NewsRun>>(runsPath, { signal: controller.signal }),
          newsRequest<NewsPaged<NewsRunItem>>(itemsPath, { signal: controller.signal }),
        ]);
        if (controller.signal.aborted) return;
        setJob(nextJob); setRuns(nextRuns); setItems(nextItems); setError("");
        const sourceStillRunning = nextJob.status === "completed" && nextRuns.items.some(run => run.status === "running");
        if (active(nextJob.status) || sourceStillRunning || nextItems.items.some(item => active(item.analysis_status))) timer = setTimeout(refresh, 2500);
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof NewsRequestError && reason.status === 401) { router.replace("/admin/login"); router.refresh(); }
        setError(reason instanceof NewsRequestError ? reason.message : "Не удалось обновить отчёт. Повторите запрос.");
      }
    }
    void refresh();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [initialJob, initialRuns, initialItems, runsPath, itemsPath, attempt, router]);

  const path = `/admin/news/jobs/${job.slug}`;
  return <div className="news-stack news-run-report">
    <NewsJobProgress jobSlug={job.slug} initialJob={job} polling={false} showLink={false} />
    <RunTimes started={job.started_at} completed={job.completed_at} />
    <div><button className="admin-button" type="button" onClick={() => setAttempt(value => value + 1)}>Обновить отчёт</button></div>
    <NewsFeedback error={error} />
    <section className="admin-section news-stack" aria-labelledby="news-report-sources"><h2 id="news-report-sources">Обходы источников</h2>
      {runs.items.length ? <ul className="news-run-list">{runs.items.map(run => <li key={run.id}><SourceRun run={run} /></li>)}</ul> : <p className="admin-empty">Обходы источников ещё не начались.</p>}
      <AdminPagination path={path} page={runs.page} pages={runs.pages ?? Math.ceil(runs.total / runs.page_size)} total={runs.total} pageParam="runs_page" label="Страницы обходов источников" params={{ ...filters, page: items.page }} />
    </section>
    <section className="admin-section news-stack" aria-labelledby="news-report-items"><h2 id="news-report-items">Материалы этого запуска</h2>
      <p className="admin-muted">Результат сбора и статус анализа относятся к версии, проверенной в этом запуске. Карточка материала содержит его текущую версию.</p>
      <form action={path} method="get" className="admin-filters news-filters">
        <input type="hidden" name="runs_page" value={runs.page} />
        <div className="admin-field"><label htmlFor="news-run-source">Источник</label><select id="news-run-source" name="source_slug" defaultValue={filters.source_slug}><option value="">Все источники</option>{sources.map(source => <option key={source.slug} value={source.slug}>{source.name}</option>)}</select></div>
        <div className="admin-field"><label htmlFor="news-run-outcome">Результат сбора</label><select id="news-run-outcome" name="outcome" defaultValue={filters.outcome}><option value="">Все результаты</option>{Object.entries(runOutcomeLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <label className="news-check"><input type="checkbox" name="warnings_only" value="true" defaultChecked={filters.warnings_only === "true"} />Только с предупреждениями</label>
        <button className="admin-button" type="submit">Применить</button><Link className="admin-button" prefetch={false} href={adminHref(path, { runs_page: runs.page })}>Сбросить</Link>
      </form>
      {items.items.length ? <ul className="news-run-list" aria-label="Материалы запуска">{items.items.map(item => <li key={item.id}><RunItem item={item} /></li>)}</ul> : <p className="admin-empty">Материалов по этим фильтрам пока нет.</p>}
      <AdminPagination path={path} page={items.page} pages={items.pages ?? Math.ceil(items.total / items.page_size)} total={items.total} label="Страницы материалов запуска" params={{ ...filters, runs_page: runs.page }} />
    </section>
  </div>;
}
