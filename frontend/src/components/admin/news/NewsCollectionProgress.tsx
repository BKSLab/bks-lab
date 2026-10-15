"use client";

import Link from "next/link";
import type { NewsCollectionStatus } from "@/lib/news-api/types";

function progressTitle(status: NewsCollectionStatus) {
  if (status.job?.status === "queued") return "Проверка в очереди";
  if (status.job?.status === "running") return "Проверяем источники";
  if (status.busy) return "Сбор завершён, идёт анализ";
  if (status.job?.status === "cancelled") return "Проверка отменена";
  if (status.job?.status === "failed" || status.collection.sources_failed || status.analysis.failed) return "Проверка завершена с ошибками";
  if (status.analysis.blocked) return "Сбор завершён, часть материалов ожидает анализа";
  return "Проверка завершена";
}

export function NewsCollectionProgress({ status, awaiting = false, requestedJob = null, error, onRetry }: {
  status: NewsCollectionStatus;
  awaiting?: boolean;
  requestedJob?: string | null;
  error: string;
  onRetry: () => void;
}) {
  const { job, collection, analysis } = status;
  const currentNames = status.sources.filter(source => source.status === "running").map(source => source.source_name);
  const otherJobs = status.active_jobs - Number(job?.status === "queued" || job?.status === "running");
  return <section className="news-collection-progress news-stack" aria-label="Ход проверки публикаций">
    {error && <div className="news-collection-connection"><p role="status">{error} Показано последнее полученное состояние.</p><button className="admin-button" type="button" onClick={onRetry}>Обновить состояние</button></div>}
    {awaiting ? <><p className="news-collection-title" role="status">Запуск принят. Получаем состояние проверки…</p>{requestedJob && <Link className="admin-link" prefetch={false} href={`/admin/news/jobs/${requestedJob}`}>Открыть отчёт</Link>}</>
      : !job ? <p className="admin-muted">Проверок ещё не было. Включите нужные источники и запустите сбор.</p>
        : <>
          <div className="news-collection-heading"><p className="news-collection-title" role="status">{progressTitle(status)}</p><Link className="admin-link" prefetch={false} href={`/admin/news/jobs/${job.slug}`}>Открыть отчёт</Link></div>
          {job.source_name && <p className="admin-muted">{job.source_name}</p>}
          <div className="news-collection-stages">
            <div className="news-collection-stage">
              <h2>Сбор материалов</h2>
              <p>Проверено <strong>{collection.sources_done} из {collection.sources_total}</strong> источников</p>
              <progress aria-label="Проверенные источники" max={Math.max(collection.sources_total, 1)} value={collection.sources_done} />
              <p className="admin-muted">Новых: <strong>{collection.new}</strong> · Обновлено: <strong>{collection.updated}</strong> · Без изменений: {collection.unchanged}</p>
              {currentNames.length > 0 && <p className="news-collection-current">Проверяются: {currentNames.join(", ")}</p>}
              {collection.sources_queued > 0 && <p className="admin-muted">Ожидают проверки: {collection.sources_queued}</p>}
              {(collection.sources_failed > 0 || collection.warnings > 0) && <p className="admin-error">Ошибок источников: {collection.sources_failed} · Предупреждений: {collection.warnings}</p>}
            </div>
            <div className="news-collection-stage">
              <h2>Анализ материалов</h2>
              {analysis.total > 0 ? <>
                <p>Готово <strong>{analysis.completed} из {analysis.total}</strong> анализов</p>
                <progress aria-label="Готовые анализы" max={analysis.total} value={analysis.completed} />
                <p className="admin-muted">Новые и изменённые материалы. В работе: {analysis.running} · В очереди: {analysis.queued + analysis.pending}</p>
                {analysis.failed > 0 && <p className="admin-error">Не удалось проанализировать: {analysis.failed}. Подробности доступны в отчёте.</p>}
                {analysis.blocked_reasons.missing_llm > 0 && <p className="admin-muted">Ожидают настройки модели: {analysis.blocked_reasons.missing_llm}.</p>}
                {analysis.blocked_reasons.paused > 0 && <p className="admin-muted">Автоматический анализ приостановлен: {analysis.blocked_reasons.paused}.</p>}
                {analysis.blocked_reasons.insufficient_text > 0 && <p className="admin-muted">Недостаточно текста для анализа: {analysis.blocked_reasons.insufficient_text}.</p>}
                {analysis.blocked_reasons.unavailable > 0 && <p className="admin-muted">Анализ недоступен для этой версии: {analysis.blocked_reasons.unavailable}.</p>}
              </> : <p className="admin-muted">{job.status === "queued" || job.status === "running" ? "Материалы ещё собираются. Анализ начнётся после их сохранения." : "Новых и изменённых материалов для анализа нет."}</p>}
            </div>
          </div>
          {job.error && <p className="admin-error">{job.error}</p>}
          {otherJobs > 0 && <p className="admin-muted">Других заданий сбора: {otherJobs}. Их ход доступен в истории проверок.</p>}
        </>}
  </section>;
}
