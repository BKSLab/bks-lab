import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTimeSeries } from "@/components/admin/AdminTimeSeries";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate, adminNumber, contentStatusLabels, contentTypeLabels } from "@/lib/admin-api/params";
import type { AdminContentDetail } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Карточка материала" };

export default async function AdminContentDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireAdmin();
  const { id } = await params;
  if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) notFound();
  const item = await adminFetch<AdminContentDetail>(`/content/${id}`);
  const publicUrl = item.type === "article" ? `/blog/post/${encodeURIComponent(item.slug)}`
    : item.type === "project" ? `/projects/${encodeURIComponent(item.slug)}`
      : "/notes";

  return <AdminShell username={user.username} current="content">
    <header className="admin-heading">
      <p><Link className="admin-link" href="/admin/content" prefetch={false}>Все материалы</Link></p>
      <h1>{item.title}</h1>
      <p className="admin-muted">Карточка материала. Редактирование доступно через Markdown-файлы проекта.</p>
      {item.status !== "draft" && <p><Link className="admin-link" href={publicUrl}>{item.type === "note" ? "Перейти к ленте заметок" : "Открыть на сайте"}</Link></p>}
    </header>
    <dl className="admin-details">
      <dt>Тип</dt><dd>{contentTypeLabels[item.type]}</dd>
      <dt>Статус</dt><dd>{contentStatusLabels[item.status]}</dd>
      <dt>Адрес материала</dt><dd><code>{item.slug}</code></dd>
      <dt>Категория</dt><dd>{item.category ?? "Не указана"}</dd>
      <dt>Теги</dt><dd>{item.tags.length ? item.tags.join(", ") : "Нет тегов"}</dd>
      <dt>Дата публикации</dt><dd>{item.published_at ? <time dateTime={item.published_at}>{adminDate(item.published_at)}</time> : "Не указана"}</dd>
      <dt>Количество слов</dt><dd>{adminNumber(item.word_count)}</dd>
      <dt>Просмотры за 30 дней</dt><dd>{adminNumber(item.views_30d)}</dd>
      <dt>Синхронизировано, UTC</dt><dd><time dateTime={item.synced_at}>{adminDate(item.synced_at, true)}</time></dd>
      <dt>Хеш содержимого</dt><dd><code>{item.content_hash}</code></dd>
    </dl>
    <section className="admin-section" aria-labelledby="admin-content-views"><h2 id="admin-content-views">Просмотры за 30 дней</h2><AdminTimeSeries points={item.views_timeseries_30d} label="Просмотры" /></section>
  </AdminShell>;
}
