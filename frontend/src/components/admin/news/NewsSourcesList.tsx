"use client";

import { useState } from "react";
import type { NewsSource } from "@/lib/news-api/types";
import { sourceDate } from "@/lib/news-api/schedule";
import { NewsSourceSchedule } from "./NewsSourceSchedule";
import { NewsSourceToggle } from "./NewsSourceToggle";

export interface NewsSourceRowActivity {
  status: "queued" | "running" | "completed" | "failed" | "cancelled";
  new: number;
  updated: number;
  unchanged: number;
  warnings: number;
  error: string | null;
}

interface NewsSourcesListProps {
  sources: NewsSource[];
  activityBySource?: Readonly<Record<string, NewsSourceRowActivity>>;
  onCollect?: (source: NewsSource) => void;
  collectDisabled?: boolean;
  onSaved?: (source: NewsSource) => void;
}

function sourceResult(source: NewsSource, activity?: NewsSourceRowActivity): string {
  if (activity) {
    if (activity.status === "queued") return "В очереди";
    if (activity.status === "running") return "Проверяется";
    if (activity.status === "failed") return "Проверка не удалась";
    if (activity.status === "cancelled") return "Проверка отменена";
    const collected = activity.new + activity.updated;
    return collected ? `Собрано ${collected} · новых ${activity.new}` : "Без новых материалов";
  }
  if (source.last_error && source.health !== "degraded") return "Последняя проверка завершилась с ошибкой.";
  if (source.health === "degraded") return "Последняя проверка завершилась с предупреждениями.";
  if (source.last_success_at) return source.last_new_count ? `Новых материалов: ${source.last_new_count}` : "Без новых материалов";
  return "Ещё не проверялся";
}

function SourceRow({ initialSource, activity, onCollect, collectDisabled, onSaved }: {
  initialSource: NewsSource;
  activity?: NewsSourceRowActivity;
  onCollect?: NewsSourcesListProps["onCollect"];
  collectDisabled?: boolean;
  onSaved?: NewsSourcesListProps["onSaved"];
}) {
  const [saved, setSaved] = useState<{ source: NewsSource; baseline: NewsSource } | null>(null);
  const source = saved?.baseline === initialSource ? saved.source : initialSource;
  const setSource = (value: NewsSource) => { setSaved({ source: value, baseline: initialSource }); onSaved?.(value); };
  const collecting = activity?.status === "queued" || activity?.status === "running";
  const hasResults = Boolean(activity || source.last_success_at || source.last_error);
  const failed = activity ? activity.status === "failed" : Boolean(source.last_error && source.health !== "degraded");

  return <tr className="news-source-row" id={source.slug} tabIndex={-1} aria-labelledby={`source-title-${source.slug}`}>
    <th scope="row" className="admin-cell-title news-source-copy">
      <span className="news-source-name" id={`source-title-${source.slug}`}>{source.name}</span>
      <p className="admin-muted news-source-description">{source.description}</p>
    </th>
    <td data-label="Регулярно"><NewsSourceToggle source={source} onSaved={setSource} /></td>
    <td data-label="Расписание"><NewsSourceSchedule source={source} onSaved={setSource} /></td>
    <td data-label="Проверка" className="news-source-check">
      <p className="news-source-next"><span className="admin-muted">Следующая: </span>{!source.active ? "на паузе" : source.next_check_at ? <time dateTime={source.next_check_at}>{sourceDate(source.next_check_at)}</time> : "не запланирована"}</p>
      <p className={failed ? "admin-error" : "admin-muted"}>{sourceResult(source, activity)}</p>
      {activity?.error && <p className={failed ? "admin-error" : "admin-muted"}>{activity.error}</p>}
      {activity && activity.warnings > 0 && <p className="admin-muted">Предупреждений: {activity.warnings}</p>}
    </td>
    <td data-label="Действия"><div className="news-source-actions">
      {onCollect && <button className="admin-button" type="button" disabled={collectDisabled || collecting} aria-label={`Проверить: ${source.name}`} onClick={() => onCollect(source)}>Проверить</button>}
      {hasResults && <a className="admin-link" href={`/admin/news/runs?source_slug=${encodeURIComponent(source.slug)}`} aria-label={`Последние результаты: ${source.name}`}>Результаты</a>}
      {!onCollect && !hasResults && <span className="admin-muted">—</span>}
    </div></td>
  </tr>;
}

export function NewsSourcesList({ sources, activityBySource, onCollect, collectDisabled, onSaved }: NewsSourcesListProps) {
  return sources.length ? <table className="admin-table admin-card-table news-sources-table" role="table">
    <caption>Готовые источники. Расписание и время проверок — по Самаре (UTC+4).</caption>
    <thead><tr><th scope="col">Источник</th><th scope="col">Регулярно</th><th scope="col">Расписание</th><th scope="col">Проверка</th><th scope="col">Действия</th></tr></thead>
    <tbody>{sources.map(source => <SourceRow key={source.id} initialSource={source} activity={activityBySource?.[source.slug]} onCollect={onCollect} collectDisabled={collectDisabled} onSaved={onSaved} />)}</tbody>
  </table> : <p className="admin-empty">Готовых источников пока нет.</p>;
}
