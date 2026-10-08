"use client";

import { useId, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { decisionLabels, formatLabels } from "@/lib/news-api/params";
import type { NewsDecision, NewsDecisionValue, NewsFormat } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

export function NewsDecisionForm({ itemId, current, defaultFormat = "longread_candidate", compact = false }: {
  itemId: number; current?: NewsDecision | null; defaultFormat?: NewsFormat; compact?: boolean;
}) {
  const router = useRouter();
  const id = useId();
  const mutation = useNewsMutation();
  const [decision, setDecision] = useState(current?.decision);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const value = submitter?.value as NewsDecisionValue;
    if (!value || !(value in decisionLabels)) return;
    const form = new FormData(event.currentTarget);
    const result = await mutation.run<NewsDecision>(`/items/${itemId}/decision`, { decision: value, format: form.get("format"), comment: String(form.get("comment") ?? "").trim() });
    if (result) { setDecision(value); mutation.setMessage(`Решение сохранено: ${decisionLabels[value].toLowerCase()}.`); router.refresh(); }
  }
  const fields = <>
    <div className="admin-field"><label htmlFor={`${id}-format`}>Назначение</label><select name="format" id={`${id}-format`} defaultValue={current?.format ?? defaultFormat} disabled={mutation.pending}>
      {Object.entries(formatLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></div>
    <div className="admin-field"><label htmlFor={`${id}-comment`}>Комментарий редактора</label><textarea id={`${id}-comment`} name="comment" rows={compact ? 2 : 3} maxLength={2000} defaultValue={current?.comment ?? ""} disabled={mutation.pending} /></div>
    <div className="news-actions">
      <button type="submit" className="admin-button admin-button-primary" value="in_work" disabled={mutation.pending}>В работу</button>
      <button type="submit" className="admin-button" value="deferred" disabled={mutation.pending}>Отложить</button>
      <button type="submit" className="admin-button" value="rejected" disabled={mutation.pending}>Отклонить</button>
    </div>
  </>;
  return <form onSubmit={submit} className="news-decision" aria-label={`Решение по материалу № ${itemId}`} aria-busy={mutation.pending}>
    {decision && <p className="admin-muted">Решение: {decisionLabels[decision]}</p>}
    {compact ? <details><summary>Редакторское решение</summary><div className="news-stack">{fields}</div></details> : fields}
    <NewsFeedback {...mutation} />
  </form>;
}
