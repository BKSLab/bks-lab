"use client";

import { useRouter } from "next/navigation";
import type { NewsSource } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

export function NewsSourceToggle({ source }: { source: NewsSource }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  return <div>
    <button className="admin-button" type="button" disabled={mutation.pending} aria-label={`${source.active ? "Приостановить" : "Включить"} источник ${source.name}`} onClick={async () => {
      const result = await mutation.run(`/sources/${source.id}`, { active: !source.active }, "PATCH");
      if (result) { mutation.setMessage(source.active ? "Источник приостановлен." : "Источник включён."); router.refresh(); }
    }}>{source.active ? "Приостановить" : "Включить"}</button>
    <NewsFeedback {...mutation} />
  </div>;
}
