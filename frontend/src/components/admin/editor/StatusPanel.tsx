"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { contentRequest, ContentRequestError } from "@/lib/admin-api/content-client";
import { contentStatusLabels } from "@/lib/admin-api/params";
import type { AdminContentDetail, ContentStatus } from "@/lib/admin-api/types";

export function StatusPanel({ item, onChanged }: { item: AdminContentDetail; onChanged: (item: AdminContentDetail) => void }) {
  const router = useRouter();
  const allowed: ContentStatus[] = item.type === "project" ? ["draft", "active", "archived"] : ["draft", "active"];
  const [status, setStatus] = useState<ContentStatus>(item.status);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function applyStatus() {
    setPending(true);
    setError("");
    setMessage("");
    try {
      const updated = await contentRequest<AdminContentDetail>(`/${item.id}/status`, { method: "POST", body: { status } });
      setStatus(updated.status);
      setMessage(`Статус изменён на «${contentStatusLabels[updated.status]}».`);
      onChanged(updated);
      router.refresh();
    } catch (reason) {
      setError(reason instanceof ContentRequestError ? reason.message : "Не удалось изменить статус.");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="editor-status" aria-label="Статус публикации">
      <h2 className="editor-section-heading">Статус</h2>
      <div className="editor-status-row">
        <div className="admin-field">
          <label htmlFor="editor-status-select">Текущий статус</label>
          <select id="editor-status-select" value={status} onChange={(event) => setStatus(event.target.value as ContentStatus)} disabled={pending}>
            {allowed.map((value) => <option key={value} value={value}>{contentStatusLabels[value]}</option>)}
          </select>
        </div>
        <button type="button" className="admin-button" onClick={applyStatus} disabled={pending || status === item.status} aria-busy={pending}>
          {pending ? "Меняем статус…" : "Применить статус"}
        </button>
      </div>
      {error && <p className="admin-error" role="alert">{error}</p>}
      {message && <p className="admin-muted" role="status">{message}</p>}
      <p className="admin-muted">Черновики не видны на сайте. Архив доступен только проектам.</p>
    </section>
  );
}
