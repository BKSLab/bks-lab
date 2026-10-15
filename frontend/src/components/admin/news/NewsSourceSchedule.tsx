"use client";

import { type FormEvent, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sourceScheduleError, sourceToday, sourceWeekdays } from "@/lib/news-api/schedule";
import type { NewsSource, NewsSourceSchedule as SourceSchedule } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

export function NewsSourceSchedule({ source, onSaved }: { source: NewsSource; onSaved: (source: NewsSource) => void }) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const details = useRef<HTMLDetailsElement>(null);
  const summary = useRef<HTMLElement>(null);
  const [mode, setMode] = useState<SourceSchedule["mode"]>(source.schedule.mode);
  const [times, setTimes] = useState(source.schedule.times);
  const [everyDays, setEveryDays] = useState(source.schedule.mode === "interval_days" ? String(source.schedule.every_days) : "3");
  const [startDate, setStartDate] = useState(source.schedule.mode === "interval_days" ? source.schedule.start_date : sourceToday);
  const [weekdays, setWeekdays] = useState(source.schedule.mode === "weekly" ? source.schedule.weekdays : [0]);
  const prefix = `source-schedule-${source.slug}`;

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const schedule: SourceSchedule = mode === "daily" ? { mode, times }
      : mode === "weekly" ? { mode, times, weekdays: [...weekdays].sort((a, b) => a - b) }
      : { mode, times, every_days: Number(everyDays), start_date: startDate };
    const error = sourceScheduleError(schedule);
    if (error) { mutation.setError(error); return; }
    const result = await mutation.run<NewsSource>(`/sources/${source.slug}`, { schedule: { ...schedule, times: [...times].sort() } }, "PATCH");
    if (result) {
      onSaved(result);
      mutation.setMessage("Расписание сохранено.");
      if (details.current) details.current.open = false;
      summary.current?.focus();
      router.refresh();
    }
  }

  return <div className="news-stack">
    <details className="news-source-schedule" ref={details} onToggle={event => {
      if (!event.currentTarget.open) return;
      setMode(source.schedule.mode); setTimes(source.schedule.times);
      setEveryDays(source.schedule.mode === "interval_days" ? String(source.schedule.every_days) : "3");
      setStartDate(source.schedule.mode === "interval_days" ? source.schedule.start_date : sourceToday());
      setWeekdays(source.schedule.mode === "weekly" ? source.schedule.weekdays : [0]);
      mutation.setError(""); mutation.setMessage("");
    }}>
      <summary ref={summary} aria-label={`Изменить расписание: ${source.name}`}>Изменить расписание</summary>
      <form className="news-stack" onSubmit={save} aria-label={`Расписание: ${source.name}`} aria-busy={mutation.pending}>
        <fieldset className="news-fieldset" disabled={mutation.pending}>
          <legend>Расписание проверки</legend>
          <p className="admin-muted">Время Самары (UTC+4).</p>
          <div className="admin-field"><label htmlFor={`${prefix}-mode`}>Как часто проверять</label><select id={`${prefix}-mode`} value={mode} onChange={event => setMode(event.target.value as SourceSchedule["mode"])}>
            <option value="daily">Каждый день</option><option value="interval_days">Раз в несколько дней</option><option value="weekly">В выбранные дни недели</option>
          </select></div>
          {mode === "interval_days" && <div className="news-fields-two">
            <div className="admin-field"><label htmlFor={`${prefix}-every`}>Через сколько дней (обязательно)</label><input id={`${prefix}-every`} type="number" min={1} max={365} step={1} required value={everyDays} onChange={event => setEveryDays(event.target.value)} /></div>
            <div className="admin-field"><label htmlFor={`${prefix}-start`}>Первый день расписания (обязательно)</label><input id={`${prefix}-start`} type="date" required value={startDate} onChange={event => setStartDate(event.target.value)} aria-describedby={`${prefix}-start-help`} /><p className="admin-muted" id={`${prefix}-start-help`}>Проверки повторяются через указанное число дней, начиная с этой даты.</p></div>
          </div>}
          {mode === "weekly" && <fieldset className="news-source-weekdays"><legend>Дни недели (хотя бы один)</legend><div className="news-checks">{sourceWeekdays.map((day, index) => <label className="news-check" key={day}><input type="checkbox" checked={weekdays.includes(index)} onChange={event => setWeekdays(current => event.target.checked ? [...current, index] : current.filter(value => value !== index))} />{day}</label>)}</div></fieldset>}
          <fieldset className="news-source-times"><legend>Время проверки (от 1 до 12)</legend><div className="news-stack">{times.map((time, index) => <div className="news-source-time" key={index}>
            <div className="admin-field"><label htmlFor={`${prefix}-time-${index}`}>Время {index + 1} (обязательно)</label><input id={`${prefix}-time-${index}`} type="time" required value={time} onChange={event => setTimes(current => current.map((value, position) => position === index ? event.target.value : value))} /></div>
            {times.length > 1 && <button className="admin-button" type="button" onClick={() => setTimes(current => current.filter((_, position) => position !== index))} aria-label={`Удалить время ${index + 1}`}>Удалить</button>}
          </div>)}</div><button className="admin-button" type="button" disabled={times.length >= 12} onClick={() => setTimes(current => [...current, ""])}>Добавить время</button></fieldset>
          <div className="news-actions"><button className="admin-button admin-button-primary" type="submit">{mutation.pending ? "Сохраняем…" : "Сохранить расписание"}</button><button className="admin-button" type="button" onClick={() => { if (details.current) details.current.open = false; summary.current?.focus(); }}>Отмена</button></div>
        </fieldset>
        {mutation.error && <NewsFeedback error={mutation.error} />}
      </form>
    </details>
    {mutation.message && <p className="admin-muted" role="status">{mutation.message}</p>}
  </div>;
}
