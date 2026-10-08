"use client";

import { type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { scoreLabels } from "@/lib/news-api/params";
import type { NewsScores, NewsSettings } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

const limits = [
  ["initial_lookback_days", "Первый обход: глубина, дней", 1, 365],
  ["max_items_per_source", "Материалов на источник за обход", 1, 200],
  ["max_excerpt_chars", "Символов текста для модели", 500, 12000],
  ["analysis_batch_size", "Материалов в одном пакете анализа", 1, 200],
  ["text_retention_days", "Хранение текстов, дней", 1, 3650],
  ["history_retention_days", "Хранение истории, дней", 1, 3650],
] as const;

function Weights({ name, label, values, disabled }: { name: string; label: string; values: NewsScores; disabled: boolean }) {
  return <fieldset className="news-fieldset" disabled={disabled}><legend>{label}</legend><p className="admin-muted">Сумма четырёх весов — 100; все поля обязательны.</p><div className="news-fields-two">{Object.entries(scoreLabels).map(([key, title]) => <div className="admin-field" key={key}>
    <label htmlFor={`${name}-${key}`}>{title}, %</label><input id={`${name}-${key}`} type="number" name={`${name}.${key}`} min={0} max={100} step={1} required defaultValue={values[key as keyof NewsScores]} />
  </div>)}</div></fieldset>;
}

export function NewsSettingsForm({ settings }: { settings: NewsSettings }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const weights = (name: string) => Object.fromEntries(Object.keys(scoreLabels).map(key => [key, Number(data.get(`${name}.${key}`))])) as NewsScores;
    const newsWeights = weights("news_weights"), articleWeights = weights("article_weights");
    if ([newsWeights, articleWeights].some(values => Object.values(values).some(value => !Number.isInteger(value) || value < 0 || value > 100) || Object.values(values).reduce((sum, value) => sum + value, 0) !== 100)) {
      mutation.setError("Сумма весов должна равняться 100 отдельно для новостей и статей."); return;
    }
    const timezone = String(data.get("timezone") ?? "").trim();
    try { new Intl.DateTimeFormat("ru-RU", { timeZone: timezone }).format(); }
    catch { mutation.setError("Укажите существующий часовой пояс, например Europe/Samara."); return; }
    const schedule = [0, 1, 2].map(index => String(data.get(`schedule-${index}`)));
    if (new Set(schedule).size !== 3) { mutation.setError("Укажите три разных времени запуска."); return; }
    const result = await mutation.run<NewsSettings>("/settings", {
      enabled: data.has("enabled"), timezone, schedule,
      editorial_policy: String(data.get("editorial_policy") ?? "").trim(), exclusions: String(data.get("exclusions") ?? "").trim(),
      news_weights: newsWeights, article_weights: articleWeights,
      ...Object.fromEntries(limits.map(([key]) => [key, Number(data.get(key))])),
    }, "PATCH");
    if (result) { mutation.setMessage("Настройки сохранены. Следующие задания используют новые параметры."); router.refresh(); }
  }
  return <form className="news-form" onSubmit={save} aria-busy={mutation.pending}>
    <section className="admin-section news-stack" aria-labelledby="news-model-heading"><h2 id="news-model-heading">Модель анализа</h2>
      <p><span className="admin-status">{settings.llm_configured ? "Настроена" : "Не настроена"}</span></p>
      <p className="admin-muted">{settings.llm_configured ? `${settings.llm_provider} · ${settings.llm_model}` : "Материалы будут собираться и ожидать анализа до подключения модели."}</p>
      <p className="admin-muted">Модель меняется в серверной настройке NEWS_LLM_MODEL.</p>
    </section>
    <fieldset className="news-fieldset" disabled={mutation.pending}><legend>Сбор и расписание</legend>
      <label className="news-check"><input type="checkbox" name="enabled" defaultChecked={settings.enabled} />Включить сбор по расписанию</label>
      <div className="admin-field"><label htmlFor="news-timezone">Часовой пояс (обязательно)</label><input id="news-timezone" name="timezone" defaultValue={settings.timezone} placeholder="Europe/Samara" required maxLength={100} /></div>
      <p className="admin-muted">Три запуска в сутки в выбранном часовом поясе. Все три времени обязательны.</p>
      <div className="news-fields-three">{[0, 1, 2].map(index => <div className="admin-field" key={index}><label htmlFor={`news-schedule-${index}`}>Запуск {index + 1}</label><input id={`news-schedule-${index}`} type="time" name={`schedule-${index}`} defaultValue={settings.schedule[index]} required /></div>)}</div>
    </fieldset>
    <fieldset className="news-fieldset" disabled={mutation.pending}><legend>Редакционная политика</legend>
      <div className="admin-field"><label htmlFor="news-policy">Тематика, аудитория и критерии отбора (обязательно)</label><textarea id="news-policy" name="editorial_policy" defaultValue={settings.editorial_policy} rows={7} required maxLength={12000} /></div>
      <div className="admin-field"><label htmlFor="news-exclusions">Исключения</label><textarea id="news-exclusions" name="exclusions" defaultValue={settings.exclusions} rows={4} maxLength={6000} /></div>
    </fieldset>
    <div className="news-fields-two"><Weights name="news_weights" label="Рейтинг короткой новости" values={settings.news_weights} disabled={mutation.pending} /><Weights name="article_weights" label="Рейтинг для статьи" values={settings.article_weights} disabled={mutation.pending} /></div>
    <fieldset className="news-fieldset" disabled={mutation.pending}><legend>Объём и хранение</legend><p className="admin-muted">Все значения обязательны. Старые тексты и записи истории очищаются фоновым обработчиком.</p><div className="news-fields-two">{limits.map(([key, label, min, max]) => <div className="admin-field" key={key}>
      <label htmlFor={`news-setting-${key}`}>{label}</label><input id={`news-setting-${key}`} name={key} type="number" min={min} max={max} step={1} required defaultValue={settings[key]} />
    </div>)}</div></fieldset>
    <NewsFeedback {...mutation} />
    <div><button className="admin-button admin-button-primary" type="submit" disabled={mutation.pending}>{mutation.pending ? "Сохраняем…" : "Сохранить настройки"}</button></div>
  </form>;
}
