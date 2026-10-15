"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { NewsJobAccepted, NewsSource } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";
import { NewsJobProgress } from "./NewsJobProgress";

export function NewsJobLauncher({ sources, sourceSlug, sourceName, itemId, allActive = false }: { sources?: NewsSource[]; sourceSlug?: string; sourceName?: string; itemId?: number; allActive?: boolean }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const [jobSlug, setJobSlug] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [selectedSource, setSelectedSource] = useState("");
  async function start() {
    if (running) return;
    const chosenSource = sourceSlug ?? selectedSource;
    const result = await mutation.run<NewsJobAccepted>(itemId ? `/items/${itemId}/reanalyze` : "/jobs/collect", itemId ? {} : { ...(chosenSource ? { source_slug: chosenSource } : {}) });
    if (result) { setJobSlug(result.job_slug); setRunning(true); }
  }
  return <div className="news-stack">
    <div className="news-actions">
      {sources && <div className="admin-field"><label htmlFor="news-collect-source">Источник для сбора</label><select id="news-collect-source" value={selectedSource} onChange={event => setSelectedSource(event.target.value)} disabled={mutation.pending || running}>
        <option value="">Все активные источники</option>{sources.map(source => <option value={source.slug} key={source.slug}>{source.name}{!source.active ? " (на паузе)" : ""}</option>)}
      </select></div>}
      <button className="admin-button" type="button" onClick={start} disabled={mutation.pending || running} aria-label={sourceName ? `Проверить сейчас: ${sourceName}` : undefined}>
        {mutation.pending ? "Создаём задание…" : itemId ? "Повторить анализ" : allActive ? "Проверить все включённые" : "Проверить сейчас"}
      </button>
    </div>
    <NewsFeedback error={mutation.error} />
    {jobSlug && <NewsJobProgress key={jobSlug} jobSlug={jobSlug} onFinish={() => { setRunning(false); router.refresh(); }} />}
  </div>;
}
