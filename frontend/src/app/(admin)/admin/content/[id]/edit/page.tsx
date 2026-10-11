import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { AdminShell } from "@/components/admin/AdminShell";
import { ContentEditorForm } from "@/components/admin/editor/ContentEditorForm";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { contentTypeLabels } from "@/lib/admin-api/params";
import type { AdminContentDetail } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Правка материала" };

export default async function AdminContentEditPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireAdmin();
  const { id } = await params;
  if (!/^[1-9]\d*$/.test(id) || !Number.isSafeInteger(Number(id))) notFound();
  const item = await adminFetch<AdminContentDetail>(`/content/${id}`);

  return <AdminShell username={user.username} current="content">
    <header className="admin-heading">
      <p><Link className="admin-link" href={`/admin/content/${item.id}`} prefetch={false}>К карточке материала</Link></p>
      <h1>Правка: {item.title}</h1>
      <p className="admin-muted">{contentTypeLabels[item.type]}. Адрес: <code>{item.slug}</code>. Каждое сохранение записывает версию.</p>
    </header>
    <ContentEditorForm key={`${item.id}-${item.updated_at}`} mode="edit" item={item} />
  </AdminShell>;
}
