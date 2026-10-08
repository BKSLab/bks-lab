"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { newsRequest, NewsRequestError } from "@/lib/news-api/client";

export function useNewsMutation() {
  const router = useRouter();
  const busy = useRef(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function run<T>(path: string, body: unknown, method: "POST" | "PATCH" = "POST"): Promise<T | null> {
    if (busy.current) return null;
    busy.current = true;
    setPending(true); setError(""); setMessage("");
    try { return await newsRequest<T>(path, { method, body }); }
    catch (reason) {
      if (reason instanceof NewsRequestError && reason.status === 401) {
        router.replace("/admin/login"); router.refresh();
      }
      setError(reason instanceof NewsRequestError ? reason.message : "Не удалось выполнить действие. Попробуйте снова.");
      return null;
    } finally { busy.current = false; setPending(false); }
  }
  return { pending, error, message, setError, setMessage, run };
}

export function NewsFeedback({ error, message = "", pending = false }: { error: string; message?: string; pending?: boolean }) {
  const errorRef = useRef<HTMLParagraphElement>(null);
  useEffect(() => { if (error) errorRef.current?.focus(); }, [error]);
  return <>
    {error && <p className="admin-error news-feedback" role="alert" tabIndex={-1} ref={errorRef}>{error}</p>}
    <p className="admin-muted news-feedback" role="status">{pending ? "Сохраняем…" : message}</p>
  </>;
}
