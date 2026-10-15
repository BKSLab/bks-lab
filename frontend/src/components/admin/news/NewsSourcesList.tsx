"use client";

import { useState } from "react";
import type { NewsSource } from "@/lib/news-api/types";
import { sourceDate, sourceScheduleSummary } from "@/lib/news-api/schedule";
import { NewsJobLauncher } from "./NewsJobLauncher";
import { NewsSourceSchedule } from "./NewsSourceSchedule";
import { NewsSourceToggle } from "./NewsSourceToggle";

function SourceRow({ initialSource }: { initialSource: NewsSource }) {
  const [saved, setSaved] = useState<{ source: NewsSource; baseline: NewsSource } | null>(null);
  const source = saved?.baseline === initialSource ? saved.source : initialSource;
  const setSource = (value: NewsSource) => setSaved({ source: value, baseline: initialSource });
  return <article className="news-source-row" id={source.slug} tabIndex={-1} aria-labelledby={`source-title-${source.slug}`}>
    <div className="news-source-copy news-stack">
      <h2 id={`source-title-${source.slug}`}>{source.name}</h2>
      <p className="admin-muted">{source.description}</p>
      {source.health === "degraded" ? <p className="admin-muted">Последняя проверка завершилась с предупреждениями.</p> : source.last_error ? <p className="admin-error">Последняя проверка завершилась с ошибкой. Повторите её позже.</p> : null}
    </div>
    <div className="news-source-controls news-stack">
      <NewsSourceToggle source={source} onSaved={setSource} />
      <div className="news-stack"><p>{sourceScheduleSummary(source.schedule)}</p><NewsSourceSchedule source={source} onSaved={setSource} /></div>
      <p className="news-item-meta">Следующая проверка: {!source.active ? "на паузе" : source.next_check_at ? <time dateTime={source.next_check_at}>{sourceDate(source.next_check_at)}</time> : "не запланирована"}</p>
      <div className="news-actions"><NewsJobLauncher sourceSlug={source.slug} sourceName={source.name} />{(source.last_success_at || source.last_error) && <a className="admin-link" href={`/admin/news/runs?source_slug=${encodeURIComponent(source.slug)}`} aria-label={`Последние результаты: ${source.name}`}>Последние результаты</a>}</div>
    </div>
  </article>;
}

export function NewsSourcesList({ sources }: { sources: NewsSource[] }) {
  return sources.length ? <ul className="news-sources-list" aria-label="Готовые источники">{sources.map(source => <li key={source.id}><SourceRow initialSource={source} /></li>)}</ul>
    : <p className="admin-empty">Готовых источников пока нет.</p>;
}
