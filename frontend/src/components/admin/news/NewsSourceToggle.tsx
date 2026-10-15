"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import type { NewsSource } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

export function NewsSourceToggle({ source, onSaved }: { source: NewsSource; onSaved?: (source: NewsSource) => void }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const [local, setLocal] = useState<{ active: boolean; baseline: NewsSource } | null>(null);
  const active = local?.baseline === source ? local.active : source.active;
  return <div className="news-source-toggle">
    <button className="news-source-switch" role="switch" aria-checked={active} type="button" disabled={mutation.pending} aria-label={`Регулярная проверка: ${source.name}`} onClick={async () => {
      const previous = active;
      setLocal({ active: !previous, baseline: source });
      const result = await mutation.run<NewsSource>(`/sources/${source.slug}`, { active: !previous }, "PATCH");
      if (result) { setLocal({ active: result.active, baseline: source }); onSaved?.(result); mutation.setMessage(result.active ? "Источник включён." : "Источник приостановлен."); router.refresh(); }
      else setLocal({ active: previous, baseline: source });
    }}><span className="news-source-switch-track" aria-hidden="true"><span className="news-source-switch-thumb" /></span><span aria-hidden="true">{active ? "Вкл." : "Выкл."}</span></button>
    <NewsFeedback {...mutation} />
  </div>;
}
