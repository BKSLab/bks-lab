"use client";

import { X } from "lucide-react";
import { type FormEvent, type KeyboardEvent, type RefObject, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { sourceScheduleError, sourceToday, sourceWeekdays } from "@/lib/news-api/schedule";
import type { NewsSource, NewsSourceSchedule } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

const focusableSelector = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

export function NewsSourceScheduleDialog({ source, restoreFocus, onClose, onSaved }: {
  source: NewsSource;
  restoreFocus: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  onSaved: (source: NewsSource) => void;
}) {
  const router = useRouter();
  const mutation = useNewsMutation();
  const dialog = useRef<HTMLDialogElement>(null);
  const firstField = useRef<HTMLSelectElement>(null);
  const saving = useRef(false);
  const [mode, setMode] = useState<NewsSourceSchedule["mode"]>(source.schedule.mode);
  const [times, setTimes] = useState(source.schedule.times);
  const [everyDays, setEveryDays] = useState(source.schedule.mode === "interval_days" ? String(source.schedule.every_days) : "3");
  const [startDate, setStartDate] = useState(source.schedule.mode === "interval_days" ? source.schedule.start_date : sourceToday);
  const [weekdays, setWeekdays] = useState(source.schedule.mode === "weekly" ? source.schedule.weekdays : [0]);
  const prefix = `source-schedule-${source.slug}`;

  useEffect(() => {
    const element = dialog.current;
    const trigger = restoreFocus.current;
    const previousOverflow = document.body.style.overflow;
    element?.showModal();
    document.body.style.overflow = "hidden";
    firstField.current?.focus();
    return () => {
      element?.close();
      document.body.style.overflow = previousOverflow;
      trigger?.focus();
    };
  }, [restoreFocus]);

  function dismiss() {
    if (!saving.current) onClose();
  }

  function containFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      event.stopPropagation();
      dismiss();
      return;
    }
    if (event.key !== "Tab") return;
    const element = event.currentTarget;
    const focusable = Array.from(element.querySelectorAll<HTMLElement>(focusableSelector))
      .filter(control => !control.matches(":disabled") && !control.hidden && control.tabIndex >= 0);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) {
      event.preventDefault();
      element.focus();
    } else if (event.shiftKey && (document.activeElement === first || document.activeElement === element)) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && (document.activeElement === last || document.activeElement === element)) {
      event.preventDefault();
      first.focus();
    }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving.current) return;
    const schedule: NewsSourceSchedule = mode === "daily" ? { mode, times }
      : mode === "weekly" ? { mode, times, weekdays: [...weekdays].sort((a, b) => a - b) }
      : { mode, times, every_days: Number(everyDays), start_date: startDate };
    const error = sourceScheduleError(schedule);
    if (error) { mutation.setError(error); return; }
    saving.current = true;
    dialog.current?.focus();
    const result = await mutation.run<NewsSource>(`/sources/${source.slug}`, { schedule: { ...schedule, times: [...times].sort() } }, "PATCH");
    saving.current = false;
    if (result) {
      onSaved(result);
      router.refresh();
    }
  }

  return <dialog
    ref={dialog}
    className="news-schedule-dialog"
    aria-modal="true"
    aria-labelledby={`${prefix}-title`}
    aria-describedby={`${prefix}-help`}
    tabIndex={-1}
    onKeyDown={containFocus}
    onCancel={event => { event.preventDefault(); dismiss(); }}
    onClick={event => { if (event.target === event.currentTarget) dismiss(); }}
  >
    <div className="news-schedule-panel">
      <div className="news-schedule-heading">
        <h2 id={`${prefix}-title`}>Расписание: {source.name}</h2>
        <button className="admin-button news-schedule-close" type="button" disabled={mutation.pending} onClick={dismiss} aria-label="Закрыть расписание"><X size={20} aria-hidden="true" /></button>
      </div>
      <p className="admin-muted" id={`${prefix}-help`}>Время Самары (UTC+4). Изменения применятся после сохранения.</p>
      <form className="news-stack" onSubmit={save} aria-label={`Расписание: ${source.name}`} aria-busy={mutation.pending}>
        <fieldset className="news-fieldset news-schedule-fields" disabled={mutation.pending}>
          <legend className="sr-only">Параметры расписания</legend>
          <div className="admin-field"><label htmlFor={`${prefix}-mode`}>Как часто проверять</label><select ref={firstField} id={`${prefix}-mode`} value={mode} onChange={event => setMode(event.target.value as NewsSourceSchedule["mode"])}>
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
          <div className="news-actions"><button className="admin-button admin-button-primary" type="submit">{mutation.pending ? "Сохраняем…" : "Сохранить расписание"}</button><button className="admin-button" type="button" onClick={dismiss}>Отмена</button></div>
        </fieldset>
        <NewsFeedback {...mutation} />
      </form>
    </div>
  </dialog>;
}
