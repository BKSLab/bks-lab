"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";

type Field = "name" | "email" | "message" | "consent";
type FieldErrors = Partial<Record<Field, string>>;
type Submission = { phase: "idle" | "pending" | "success" | "error"; message: string };

const labels = { name: "Имя", email: "Email", message: "Сообщение" };
const fieldLimits = { name: 100, email: 254, message: 5000 };

function responseErrors(body: unknown, fields: Field[]): FieldErrors {
  const errors: FieldErrors = {};
  if (!body || typeof body !== "object" || !("detail" in body) || !Array.isArray(body.detail)) {
    return errors;
  }
  for (const issue of body.detail) {
    const field = Array.isArray(issue?.loc) ? issue.loc.at(-1) : undefined;
    if (fields.includes(field) && field !== "consent") {
      errors[field as keyof typeof labels] = `Проверьте поле «${labels[field as keyof typeof labels]}».`;
    }
  }
  return errors;
}

export function PublicForm({ kind }: { kind: "newsletter" | "contact" }) {
  const contact = kind === "contact";
  const prefix = useId();
  const fields: (keyof typeof labels)[] = contact ? ["name", "email", "message"] : ["email"];
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submission, setSubmission] = useState<Submission>({ phase: "idle", message: "" });
  const formRef = useRef<HTMLFormElement>(null);
  const statusRef = useRef<HTMLParagraphElement>(null);
  const activeRequest = useRef<AbortController | null>(null);
  const pending = submission.phase === "pending";

  useEffect(() => () => activeRequest.current?.abort(), []);

  useEffect(() => {
    if (submission.phase === "error") {
      const first = Object.keys(errors)[0];
      const target = first ? formRef.current?.elements.namedItem(first) : statusRef.current;
      if (target instanceof HTMLElement) target.focus();
    } else if (submission.phase === "success") {
      statusRef.current?.focus();
    }
  }, [errors, submission]);

  return (
    <form
      ref={formRef}
      method="post"
      action={`/api/v1/${contact ? "feedback" : "subscribe"}`}
      noValidate
      aria-label={contact ? "Связаться с автором" : "Подписка на статьи"}
      aria-describedby={`${prefix}-notice`}
      onSubmit={async (event) => {
        event.preventDefault();
        if (activeRequest.current) return;
        const form = event.currentTarget;
        const data = new FormData(form);
        const values = Object.fromEntries(fields.map((field) => [field, String(data.get(field) ?? "").trim()]));
        const next: FieldErrors = {};
        for (const field of fields) {
          const value = values[field];
          if (!value) next[field] = `Заполните поле «${labels[field]}».`;
          else if (value.length > fieldLimits[field]) next[field] = `Не больше ${fieldLimits[field]} символов.`;
          else if (field === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
            next.email = "Укажите email в формате name@example.ru.";
          } else if (field === "message" && value.length < 10) {
            next.message = "Напишите сообщение длиной от 10 до 5000 символов.";
          }
        }
        if (data.get("consent") !== "on") next.consent = "Для отправки нужно согласие на обработку данных.";
        setErrors(next);
        if (Object.keys(next).length) {
          setSubmission({ phase: "error", message: "Проверьте отмеченные поля." });
          return;
        }

        const controller = new AbortController();
        activeRequest.current = controller;
        const timeout = window.setTimeout(() => controller.abort(), 15_000);
        setSubmission({ phase: "pending", message: "Отправка…" });
        try {
          const response = await fetch(`/api/v1/${contact ? "feedback" : "subscribe"}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...values, website: String(data.get("website") ?? "") }),
            signal: controller.signal,
          });
          const body: unknown = await response.json().catch(() => null);
          if (!response.ok) {
            if (response.status === 422) setErrors(responseErrors(body, fields));
            const message = response.status === 429
              ? "Слишком много попыток. Попробуйте снова через час."
              : response.status === 503
                ? contact
                  ? "Почта временно недоступна. Попробуйте отправить сообщение позже."
                  : "Подписка временно недоступна. Попробуйте позже."
                : response.status === 422
                  ? "Проверьте данные формы и попробуйте ещё раз."
                  : "Не удалось получить подтверждение отправки. Попробуйте позже.";
            setSubmission({ phase: "error", message });
            return;
          }
          const expected = contact ? "sent" : "subscribed";
          if (!body || typeof body !== "object" || !("status" in body) || body.status !== expected) {
            setSubmission({ phase: "error", message: "Сервис не подтвердил отправку. Попробуйте позже." });
            return;
          }
          form.reset();
          setSubmission({
            phase: "success",
            message: contact ? "Сообщение отправлено. Спасибо!" : "Email сохранён для подписки. Спасибо!",
          });
        } catch {
          setSubmission({ phase: "error", message: "Не удалось получить подтверждение. Проверьте соединение и попробуйте позже." });
        } finally {
          window.clearTimeout(timeout);
          activeRequest.current = null;
        }
      }}
      className="space-y-5"
    >
      <p id={`${prefix}-notice`} className="text-sm text-text-muted">
        {contact
          ? "Имя, email и сообщение нужны автору, чтобы ответить на ваше обращение."
          : "Сохраните email для уведомлений о новых статьях. Рассылка пока не запущена."}
      </p>
      <noscript><p className="text-sm text-text-muted">Для отправки формы включите JavaScript в браузере.</p></noscript>
      {fields.map((field) => {
        const description = [
          field === "message" ? `${prefix}-message-hint` : undefined,
          errors[field] ? `${prefix}-${field}-error` : undefined,
        ].filter(Boolean).join(" ") || undefined;
        return (
          <div key={field}>
            <label className="mb-2 block text-sm font-medium" htmlFor={`${prefix}-${field}`}>
              {labels[field]} <span className="text-text-muted">(обязательно)</span>
            </label>
            {field === "message" ? (
              <>
                <p id={`${prefix}-message-hint`} className="mb-2 text-sm text-text-muted">От 10 до 5000 символов.</p>
                <textarea
                  id={`${prefix}-${field}`}
                  name={field}
                  rows={5}
                  minLength={10}
                  maxLength={fieldLimits[field]}
                  required
                  readOnly={pending}
                  aria-invalid={Boolean(errors[field])}
                  aria-describedby={description}
                  className="form-field"
                />
              </>
            ) : (
              <input
                id={`${prefix}-${field}`}
                name={field}
                type={field === "email" ? "email" : "text"}
                autoComplete={field}
                maxLength={fieldLimits[field]}
                required
                readOnly={pending}
                aria-invalid={Boolean(errors[field])}
                aria-describedby={description}
                className="form-field"
              />
            )}
            {errors[field] && <p id={`${prefix}-${field}-error`} className="mt-2 text-sm text-error">{errors[field]}</p>}
          </div>
        );
      })}
      <div hidden aria-hidden="true">
        <label htmlFor={`${prefix}-website`}>Ваш сайт</label>
        <input id={`${prefix}-website`} name="website" type="text" tabIndex={-1} autoComplete="off" maxLength={2000} />
      </div>
      <div>
        <label className="flex min-h-11 items-start gap-3 text-sm" htmlFor={`${prefix}-consent`}>
          <input
            id={`${prefix}-consent`}
            name="consent"
            type="checkbox"
            required
            disabled={pending}
            aria-invalid={Boolean(errors.consent)}
            aria-describedby={errors.consent ? `${prefix}-consent-error` : undefined}
            className="mt-1 size-5 shrink-0 accent-accent"
          />
          <span>Согласен на обработку {contact ? "имени, email и сообщения для ответа на обращение" : "email для подписки на новые статьи"} (обязательно).</span>
        </label>
        <Link href="/privacy" className="inline-flex min-h-11 items-center text-sm text-accent underline underline-offset-4">Политика конфиденциальности</Link>
        {errors.consent && <p id={`${prefix}-consent-error`} className="mt-2 text-sm text-error">{errors.consent}</p>}
      </div>
      <button type="submit" className="button-primary" disabled={pending}>
        {pending ? "Отправка…" : contact ? "Связаться" : "Подписаться"}
      </button>
      <p
        ref={statusRef}
        role={submission.phase === "error" ? "alert" : "status"}
        tabIndex={-1}
        className={`text-sm ${submission.phase === "error" ? "text-error" : "text-text-muted"}`}
      >
        {submission.message}
      </p>
    </form>
  );
}
