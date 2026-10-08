"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import type { NewsJobAccepted, NewsSource } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";
import { NewsJobProgress } from "./NewsJobProgress";

export function NewsJobLauncher({ sources, sourceId, itemId }: { sources?: NewsSource[]; sourceId?: number; itemId?: number }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const [jobId, setJobId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [selectedSource, setSelectedSource] = useState("");
  async function start() {
    if (running) return;
    const chosenSource = sourceId ?? (selectedSource ? Number(selectedSource) : undefined);
    const result = await mutation.run<NewsJobAccepted>(itemId ? `/items/${itemId}/reanalyze` : "/jobs/collect", itemId ? {} : { ...(chosenSource ? { source_id: chosenSource } : {}) });
    if (result) { setJobId(result.job_id); setRunning(true); }
  }
  return <div className="news-stack">
    <div className="news-actions">
      {sources && <div className="admin-field"><label htmlFor="news-collect-source">Источник для сбора</label><select id="news-collect-source" value={selectedSource} onChange={event => setSelectedSource(event.target.value)} disabled={mutation.pending || running}>
        <option value="">Все активные источники</option>{sources.map(source => <option value={source.id} key={source.id}>{source.name}{!source.active ? " (на паузе)" : ""}</option>)}
      </select></div>}
      <button className="admin-button" type="button" onClick={start} disabled={mutation.pending || running}>
        {mutation.pending ? "Создаём задание…" : itemId ? "Повторить анализ" : "Проверить сейчас"}
      </button>
    </div>
    <NewsFeedback error={mutation.error} />
    {jobId && <NewsJobProgress key={jobId} jobId={jobId} onFinish={() => { setRunning(false); router.refresh(); }} />}
  </div>;
}
