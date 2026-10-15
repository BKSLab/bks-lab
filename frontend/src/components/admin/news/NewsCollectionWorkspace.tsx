"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { NewsCollectionStatus, NewsJobAccepted, NewsSource } from "@/lib/news-api/types";
import { NewsCollectionProgress } from "./NewsCollectionProgress";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";
import { NewsSourcesList } from "./NewsSourcesList";
import { useNewsCollection } from "./useNewsCollection";

export function NewsCollectionWorkspace({ initialSources, initialStatus, mode = "sources" }: {
  initialSources: NewsSource[];
  initialStatus: NewsCollectionStatus;
  mode?: "sources" | "runs";
}) {
  const router = useRouter();
  const live = useNewsCollection(initialStatus);
  const mutation = useNewsMutation();
  const [savedSources, setSavedSources] = useState<{ baseline: NewsSource[]; rows: NewsSource[] } | null>(null);
  const sources = savedSources?.baseline === initialSources ? savedSources.rows : initialSources;
  const [selectedSource, setSelectedSource] = useState("");
  const previous = useRef(initialStatus.job);
  const collecting = live.status.active_jobs > 0 || live.status.job?.status === "queued" || live.status.job?.status === "running";
  const disabled = mutation.pending || live.awaiting || collecting;
  const enabledCount = sources.filter(source => source.active).length;
  const activity = Object.fromEntries(live.status.sources.map(source => [source.source_slug, source]));

  useEffect(() => {
    const before = previous.current;
    const after = live.status.job;
    if (after && after.status !== "queued" && after.status !== "running" && (!before || before.slug !== after.slug || before.status === "queued" || before.status === "running")) router.refresh();
    previous.current = after;
  }, [live.status.job, router]);

  async function collect(sourceSlug?: string) {
    if (disabled) return;
    const result = await mutation.run<NewsJobAccepted>("/jobs/collect", sourceSlug ? { source_slug: sourceSlug } : {});
    if (result) live.watch(result.job_slug);
  }

  return <div className="news-stack news-collection-workspace">
    {sources.length > 0 && <div className="news-actions news-collection-toolbar">
      {mode === "runs" && <div className="admin-field"><label htmlFor="news-collect-source">Источник для сбора</label><select id="news-collect-source" value={selectedSource} onChange={event => setSelectedSource(event.target.value)} disabled={disabled}>
        <option value="">Все включённые источники</option>{sources.map(source => <option key={source.slug} value={source.slug}>{source.name}{source.active ? "" : " (на паузе)"}</option>)}
      </select></div>}
      <button className="admin-button" type="button" disabled={disabled || (!selectedSource && !enabledCount)} onClick={() => void collect(mode === "runs" ? selectedSource : undefined)}>
        {mutation.pending ? "Запускаем проверку…" : mode === "runs" ? "Проверить сейчас" : "Проверить все включённые"}
      </button>
      <span className="admin-muted">Включено {enabledCount} из {sources.length}</span>
      <Link className="admin-link" prefetch={false} href={mode === "sources" ? "/admin/news/runs" : "/admin/news/sources"}>{mode === "sources" ? "История проверок" : "Настроить источники"}</Link>
    </div>}
    <NewsFeedback error={mutation.error} />
    <NewsCollectionProgress status={live.status} awaiting={live.awaiting} requestedJob={live.requestedJob} error={live.error} onRetry={live.refresh} />
    {mode === "sources" && <NewsSourcesList sources={sources} activityBySource={activity} collectDisabled={disabled} onCollect={source => void collect(source.slug)} onSaved={source => setSavedSources({ baseline: initialSources, rows: sources.map(row => row.slug === source.slug ? source : row) })} />}
    {mode === "runs" && !sources.length && <p className="admin-empty">Сначала <Link className="admin-link" prefetch={false} href="/admin/news/sources">откройте источники</Link>.</p>}
  </div>;
}
