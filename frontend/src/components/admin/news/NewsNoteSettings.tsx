"use client";

import { type FormEvent, useState } from "react";
import { sourceDate } from "@/lib/news-api/schedule";
import type { NewsNoteSettings as NoteSettings } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

export function NewsNoteSettings({ settings, onSaved, onBusy }: {
  settings: NoteSettings;
  onSaved: (settings: NoteSettings) => void;
  onBusy: (busy: boolean) => void;
}) {
  const mutation = useNewsMutation();
  const [draft, setDraft] = useState<{ interval: string; age: string } | null>(null);
  const interval = draft?.interval ?? String(settings.interval_minutes);
  const age = draft?.age ?? String(settings.max_age_hours);

  async function change(body: Partial<Pick<NoteSettings, "enabled" | "interval_minutes" | "max_age_hours">>) {
    onBusy(true);
    const result = await mutation.run<NoteSettings>("/note-settings", body, "PATCH");
    onBusy(false);
    if (result) {
      if (body.interval_minutes !== undefined) setDraft(null);
      onSaved(result);
      mutation.setMessage(body.enabled === undefined ? "Настройки заметок сохранены." : result.enabled ? "Автоматическая публикация включена." : "Автоматическая публикация на паузе.");
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const intervalMinutes = Number(interval);
    const maxAgeHours = Number(age);
    if (!Number.isInteger(intervalMinutes) || intervalMinutes < 10 || intervalMinutes > 1440) {
      mutation.setError("Укажите интервал от 10 до 1440 минут целым числом."); return;
    }
    if (!Number.isInteger(maxAgeHours) || maxAgeHours < 1 || maxAgeHours > 720) {
      mutation.setError("Укажите срок актуальности от 1 до 720 часов целым числом."); return;
    }
    await change({ interval_minutes: intervalMinutes, max_age_hours: maxAgeHours });
  }

  return <section className="admin-section news-note-settings" aria-labelledby="news-note-settings-title">
    <div className="news-note-settings-heading">
      <h2 id="news-note-settings-title">Автоматическая публикация</h2>
      <button className="news-source-switch" type="button" role="switch" aria-label="Автоматическая публикация заметок" aria-checked={settings.enabled} disabled={mutation.pending} onClick={() => change({ enabled: !settings.enabled })}>
        <span className="news-source-switch-track" aria-hidden="true"><span className="news-source-switch-thumb" /></span><span aria-hidden="true">{settings.enabled ? "Включена" : "На паузе"}</span>
      </button>
    </div>
    <form onSubmit={save} className="news-note-settings-form" aria-label="Настройки заметок" aria-busy={mutation.pending}>
      <fieldset disabled={mutation.pending} className="news-note-settings-fields">
        <legend className="sr-only">Параметры публикации</legend>
        <div className="admin-field"><label htmlFor="news-note-interval">Интервал публикации, минут (обязательно)</label><input id="news-note-interval" type="number" min={10} max={1440} step={1} required value={interval} onChange={event => setDraft({ interval: event.target.value, age })} /></div>
        <div className="admin-field"><label htmlFor="news-note-age">Срок актуальности, часов (обязательно)</label><input id="news-note-age" type="number" min={1} max={720} step={1} required value={age} onChange={event => setDraft({ interval, age: event.target.value })} /></div>
        <button className="admin-button" type="submit">Сохранить настройки</button>
      </fieldset>
    </form>
    <div className="news-note-schedule admin-muted">
      {settings.last_published_at && <p>Последняя публикация: <time dateTime={settings.last_published_at}>{sourceDate(settings.last_published_at)}</time>.</p>}
      {settings.enabled && settings.next_publish_at && <p>Следующая публикация: <time dateTime={settings.next_publish_at}>{sourceDate(settings.next_publish_at)}</time>.</p>}
      {!settings.enabled && <p>Очередь сохранена. Публикации продолжатся после включения.</p>}
    </div>
    <NewsFeedback {...mutation} />
  </section>;
}
