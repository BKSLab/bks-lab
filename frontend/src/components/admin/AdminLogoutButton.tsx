"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";

export function AdminLogoutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const errorRef = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (error) errorRef.current?.focus();
  }, [error]);

  async function logout() {
    if (pending) return;
    setPending(true);
    setError("");
    try {
      const response = await fetch("/api/admin/auth/logout", {
        method: "POST",
        credentials: "same-origin",
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok && response.status !== 401) {
        setError("Не удалось выйти. Попробуйте ещё раз.");
        return;
      }
      router.replace("/admin/login");
      router.refresh();
    } catch {
      setError("Нет связи с сервером. Попробуйте выйти ещё раз.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="admin-logout">
      <button type="button" className="admin-button" onClick={logout} disabled={pending}>
        {pending ? "Выходим…" : "Выйти"}
      </button>
      {error && <p className="admin-error" role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    </div>
  );
}
