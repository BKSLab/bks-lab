"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { adminDate } from "@/lib/admin-api/params";
import { newsRequest, NewsRequestError } from "@/lib/news-api/client";
import { externalNewsUrl, jobKindLabels, jobStatusLabels, newsJobTitle } from "@/lib/news-api/params";
import type { NewsDiscovery, NewsJob } from "@/lib/news-api/types";
import { NewsFeedback } from "./NewsFeedback";

const terminal = new Set(["completed", "failed", "cancelled"]);
const counterLabels: Record<string, string> = {
  sources_total: "Источников", sources_completed: "Проверено источников", sources_processed: "Проверено источников",
  processed: "Обработано", total: "Всего", new_count: "Новых", updated_count: "Обновлено", unchanged_count: "Без изменений",
  analyzed_count: "Проанализировано", failed_count: "С ошибкой", collected: "Собрано", analyzed: "Проанализировано",
  sources_done: "Проверено источников", new: "Новых", updated: "Обновлено", unchanged: "Без изменений", errors: "С ошибкой",
  warnings: "Предупреждений", skipped_count: "Пропущено", warning_count: "Предупреждений", skipped: "Пропущено",
};

export function discoveryFromJob(job: NewsJob): NewsDiscovery | null {
  const result = job.result;
  if (job.status !== "completed" || !result || !["rss", "html"].includes(String(result.kind)) || typeof result.url !== "string" || !Array.isArray(result.items)) return null;
  return {
    kind: result.kind as NewsDiscovery["kind"], url: result.url,
    items: result.items.filter((item): item is NewsDiscovery["items"][number] => !!item && typeof item === "object" && typeof item.title === "string" && typeof item.url === "string").slice(0, 5),
    warnings: Array.isArray(result.warnings) ? result.warnings.filter((value): value is string => typeof value === "string") : [],
  };
}

export function NewsDiscoveryPreview({ preview }: { preview: NewsDiscovery }) {
  return <section className="news-preview" aria-label="Предпросмотр источника">
    <h2>Предпросмотр: {preview.kind === "rss" ? "RSS / Atom" : "HTML"}</h2>
    {preview.items.length ? <ol>{preview.items.map((item, index) => <li key={`${item.url}-${index}`}>
      <a className="admin-link" href={externalNewsUrl(item.url)} target="_blank" rel="noopener noreferrer">{item.title} <span className="sr-only">(в новой вкладке)</span></a>
      <p className="admin-muted">{adminDate(item.published_at)}</p>
    </li>)}</ol> : <p className="admin-muted">Публикации не найдены. Проверьте адрес или CSS-селекторы.</p>}
    {preview.warnings.length > 0 && <ul className="news-warnings">{preview.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul>}
  </section>;
}

export function NewsJobProgress({ jobSlug, initialJob, onFinish, showLink = true, showPreview = false, polling = true }: {
  jobSlug: string; initialJob?: NewsJob; onFinish?: (job: NewsJob) => void; showLink?: boolean; showPreview?: boolean; polling?: boolean;
}) {
  const router = useRouter();
  const [job, setJob] = useState<NewsJob | undefined>(initialJob);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const finishRef = useRef(onFinish);
  useEffect(() => { finishRef.current = onFinish; }, [onFinish]);

  useEffect(() => {
    if (!polling || (initialJob && terminal.has(initialJob.status))) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const next = await newsRequest<NewsJob>(`/jobs/${jobSlug}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setJob(next); setError("");
        if (terminal.has(next.status)) finishRef.current?.(next);
        else timer = setTimeout(poll, 2500);
      } catch (reason) {
        if (controller.signal.aborted) return;
        if (reason instanceof NewsRequestError && reason.status === 401) {
          router.replace("/admin/login"); router.refresh();
        }
        setError(reason instanceof NewsRequestError ? reason.message : "Не удалось получить состояние задания.");
      }
    }
    void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [jobSlug, initialJob, attempt, router, polling]);

  const currentJob = polling ? job : initialJob;
  const status = currentJob?.status ?? "queued";
  const counters = Object.entries(currentJob?.progress ?? {}).filter(([key, value]) => key in counterLabels && typeof value === "number" && (!["warnings", "warning_count"].includes(key) || value > 0));
  const preview = currentJob && showPreview ? discoveryFromJob(currentJob) : null;
  return <section className="news-job" aria-label={currentJob ? newsJobTitle(currentJob) : "Состояние задания"}>
    <p role="status"><strong>{currentJob ? jobKindLabels[currentJob.kind] : "Задание"}:</strong> {jobStatusLabels[status]}</p>
    {currentJob?.source_name && <p>{currentJob.source_name}</p>}
    {currentJob?.kind === "collect" && status === "completed" && <p className="admin-muted">Сбор завершён. Анализ материалов выполняется отдельно.</p>}
    {counters.length > 0 && <dl className="news-job-counts">{counters.map(([key, value]) => <div key={key}><dt>{counterLabels[key]}</dt><dd>{String(value)}</dd></div>)}</dl>}
    {currentJob?.error && <p className="admin-error">{currentJob.error}</p>}
    {status === "queued" && <p className="admin-muted">Ожидает фонового обработчика. Можно закрыть страницу и вернуться к заданию позже.</p>}
    {currentJob?.heartbeat_at && status === "running" && <p className="admin-muted">Последний сигнал: {adminDate(currentJob.heartbeat_at, true)} UTC.</p>}
    <NewsFeedback error={error} />
    {error && <button type="button" className="admin-button" onClick={() => { setError(""); setAttempt(value => value + 1); }}>Обновить статус</button>}
    {showLink && <Link className="admin-link" href={`/admin/news/jobs/${jobSlug}`} prefetch={false}>Открыть отчёт задания</Link>}
    {preview && <NewsDiscoveryPreview preview={preview} />}
  </section>;
}
