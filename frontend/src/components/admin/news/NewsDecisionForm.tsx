"use client";

import { useId, useState, type FormEvent } from "react";
import Link from "next/link";
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
  const [saved, setSaved] = useState<NewsDecision | null>(null);
  const decision = saved && (!current || saved.id >= current.id) ? saved.decision : current?.decision;
  const inPlan = decision === "in_work";
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const submitter = (event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement | null;
    const value = submitter?.value as NewsDecisionValue;
    if (!value || !(value in decisionLabels)) return;
    const form = new FormData(event.currentTarget);
    const result = await mutation.run<NewsDecision>(`/items/${itemId}/decision`, { decision: value, format: form.get("format"), comment: String(form.get("comment") ?? "").trim() });
    if (result) {
      setSaved(result);
      mutation.setMessage(value === "in_work"
        ? inPlan ? "Изменения в плане сохранены." : "Материал добавлен в план публикаций."
        : inPlan ? "Материал убран из плана публикаций." : `Решение сохранено: ${decisionLabels[value].toLowerCase()}.`);
      router.refresh();
    }
  }
  const fields = <>
    <div className="admin-field"><label htmlFor={`${id}-format`}>Назначение</label><select name="format" id={`${id}-format`} defaultValue={current?.format ?? defaultFormat} disabled={mutation.pending}>
      {Object.entries(formatLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
    </select></div>
    <div className="admin-field"><label htmlFor={`${id}-comment`}>Комментарий редактора</label><textarea id={`${id}-comment`} name="comment" rows={compact ? 2 : 3} maxLength={2000} defaultValue={current?.comment ?? ""} disabled={mutation.pending} /></div>
    <div className="news-actions">
      {inPlan && <button type="submit" className="admin-button admin-button-primary" value="in_work" disabled={mutation.pending}>Сохранить изменения в плане</button>}
      {!inPlan && <button type="submit" className="admin-button" value="deferred" disabled={mutation.pending}>Отложить</button>}
      <button type="submit" className="admin-button" value="rejected" disabled={mutation.pending}>Отклонить</button>
    </div>
  </>;
  return <form onSubmit={submit} className="news-decision" aria-label={`Решение по материалу № ${itemId}`} aria-busy={mutation.pending}>
    {decision && <p className="admin-muted">Решение: {decisionLabels[decision]}</p>}
    <div className="news-actions">
      <button type="submit" className={`admin-button${inPlan ? "" : " admin-button-primary"}`} value={inPlan ? "deferred" : "in_work"} disabled={mutation.pending}>{inPlan ? "Убрать из плана" : "Добавить в план"}</button>
      {inPlan && <Link className="admin-button" prefetch={false} href="/admin/news/plan">Открыть план публикаций</Link>}
    </div>
    {compact ? <details><summary>Редакторское решение</summary><div className="news-stack">{fields}</div></details> : fields}
    <NewsFeedback {...mutation} />
  </form>;
}
