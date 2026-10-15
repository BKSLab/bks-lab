"use client";

import { X } from "lucide-react";
import { type FormEvent, type KeyboardEvent, type RefObject, useEffect, useRef, useState } from "react";
import type { NewsNote } from "@/lib/news-api/types";
import { NewsFeedback, useNewsMutation } from "./NewsFeedback";

const focusableSelector = "button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])";

export function NewsNoteEditDialog({ note, restoreFocus, onClose, onSaved }: {
  note: NewsNote;
  restoreFocus: RefObject<HTMLButtonElement | null>;
  onClose: () => void;
  onSaved: (note: NewsNote) => void;
}) {
  const mutation = useNewsMutation();
  const dialog = useRef<HTMLDialogElement>(null);
  const firstField = useRef<HTMLInputElement>(null);
  const saving = useRef(false);
  const [title, setTitle] = useState(note.title);
  const [text, setText] = useState(note.text);
  const prefix = `news-note-${note.note_slug}`;

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

  function dismiss() { if (!saving.current) onClose(); }

  function containFocus(event: KeyboardEvent<HTMLDialogElement>) {
    if (event.key === "Escape") { event.preventDefault(); event.stopPropagation(); dismiss(); return; }
    if (event.key !== "Tab") return;
    const element = event.currentTarget;
    const focusable = Array.from(element.querySelectorAll<HTMLElement>(focusableSelector))
      .filter(control => !control.matches(":disabled") && !control.hidden && control.tabIndex >= 0);
    const first = focusable[0];
    const last = focusable.at(-1);
    if (!first || !last) { event.preventDefault(); element.focus(); }
    else if (event.shiftKey && (document.activeElement === first || document.activeElement === element)) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && (document.activeElement === last || document.activeElement === element)) { event.preventDefault(); first.focus(); }
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (saving.current) return;
    if (!title.trim() || Array.from(title).length > 90 || !text.trim() || Array.from(text).length > 300) {
      mutation.setError("Заполните заголовок до 90 символов и текст до 300 символов, включая пробелы."); return;
    }
    saving.current = true;
    dialog.current?.focus();
    const result = await mutation.run<NewsNote>(`/note-queue/${encodeURIComponent(note.note_slug)}`, { title: title.trim(), text: text.trim() }, "PATCH");
    saving.current = false;
    if (result) onSaved(result);
  }

  return <dialog ref={dialog} className="news-schedule-dialog" aria-modal="true" aria-labelledby={`${prefix}-heading`} tabIndex={-1} onKeyDown={containFocus} onCancel={event => { event.preventDefault(); dismiss(); }} onClick={event => { if (event.target === event.currentTarget) dismiss(); }}>
    <div className="news-schedule-panel news-note-dialog-panel">
      <div className="news-schedule-heading"><h2 id={`${prefix}-heading`}>Редактировать заметку</h2><button className="admin-button news-schedule-close" type="button" aria-label="Закрыть редактор заметки" disabled={mutation.pending} onClick={dismiss}><X size={20} aria-hidden="true" /></button></div>
      <form className="news-stack" aria-label="Редактирование заметки" aria-busy={mutation.pending} onSubmit={save}>
        <fieldset className="news-fieldset" disabled={mutation.pending}>
          <legend className="sr-only">Текст заметки</legend>
          <div className="admin-field"><label htmlFor={`${prefix}-title`}>Заголовок (обязательно)</label><input ref={firstField} id={`${prefix}-title`} required maxLength={90} value={title} onChange={event => setTitle(event.target.value)} aria-describedby={`${prefix}-title-count`} /><p className="admin-muted" id={`${prefix}-title-count`}>{Array.from(title).length} из 90 символов</p></div>
          <div className="admin-field"><label htmlFor={`${prefix}-text`}>Текст (обязательно)</label><textarea id={`${prefix}-text`} required maxLength={300} rows={5} value={text} onChange={event => setText(event.target.value)} aria-describedby={`${prefix}-text-count`} /><p className="admin-muted" id={`${prefix}-text-count`}>{Array.from(text).length} из 300 символов, включая пробелы</p></div>
          <div className="news-actions"><button className="admin-button admin-button-primary" type="submit">{mutation.pending ? "Сохраняем…" : "Сохранить заметку"}</button><button className="admin-button" type="button" onClick={dismiss}>Отмена</button></div>
        </fieldset>
        <NewsFeedback {...mutation} />
      </form>
    </div>
  </dialog>;
}
