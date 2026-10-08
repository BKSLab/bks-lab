"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";

export function AdminLoginForm() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const errorRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    const form = new FormData(event.currentTarget);
    const username = String(form.get("username") ?? "").trim();
    const password = String(form.get("password") ?? "");
    setError("");
    if (!username || !password) {
      setError("Заполните логин и пароль.");
      return;
    }

    setPending(true);
    try {
      const response = await fetch("/api/admin/auth/login", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) {
        setError(response.status === 401
          ? "Неверный логин или пароль. Проверьте данные и попробуйте снова."
          : response.status === 429
            ? "Слишком много попыток входа. Подождите минуту и попробуйте снова."
            : "Не удалось войти. Попробуйте ещё раз позже.");
        return;
      }
      router.replace("/admin");
      router.refresh();
    } catch {
      setError("Нет связи с сервером. Проверьте подключение и попробуйте снова.");
    } finally {
      setPending(false);
    }
  }

  return (
    <form className="admin-login-form" action="/api/admin/auth/login" method="post" onSubmit={submit} noValidate aria-busy={pending}>
      <p className="admin-muted">Все поля обязательны.</p>
      <noscript><p className="admin-error">Для входа включите JavaScript в браузере.</p></noscript>
      <div className="admin-field">
        <label htmlFor="admin-username">Логин</label>
        <input id="admin-username" name="username" autoComplete="username" required maxLength={100}
          aria-describedby={error ? "admin-login-error" : undefined} />
      </div>
      <div className="admin-field">
        <label htmlFor="admin-password">Пароль</label>
        <input id="admin-password" name="password" type="password" autoComplete="current-password" required maxLength={1024}
          aria-describedby={error ? "admin-login-error" : undefined} />
      </div>
      {error && <p id="admin-login-error" className="admin-error" role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
      <button type="submit" className="admin-button admin-button-primary" disabled={pending}>
        {pending ? "Входим…" : "Войти"}
      </button>
      <p role="status" className="admin-muted">{pending ? "Проверяем данные для входа." : ""}</p>
    </form>
  );
}
