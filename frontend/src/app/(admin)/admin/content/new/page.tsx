import type { Metadata } from "next";
import Link from "next/link";

import { AdminShell } from "@/components/admin/AdminShell";
import { ContentEditorForm } from "@/components/admin/editor/ContentEditorForm";
import { requireAdmin } from "@/lib/admin-api";
import { adminContentType, firstParam, type AdminSearchParams } from "@/lib/admin-api/params";
import type { ContentType } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Новый материал" };

const newMaterialLabels: Record<ContentType, string> = {
  article: "Новая статья",
  note: "Новая заметка",
  project: "Новый проект",
};

export default async function AdminContentNewPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const type = adminContentType(firstParam((await searchParams).type)) as ContentType | "";
  if (!type) {
    return <AdminShell username={user.username} current="content">
      <header className="admin-heading">
        <p><Link className="admin-link" href="/admin/content" prefetch={false}>Все материалы</Link></p>
        <h1>Новый материал</h1>
        <p className="admin-muted">Выберите тип материала.</p>
      </header>
      <ul className="editor-type-links">
        {(["article", "note", "project"] as const).map((value) => (
          <li key={value}><Link className="admin-button" href={`/admin/content/new?type=${value}`} prefetch={false}>{newMaterialLabels[value]}</Link></li>
        ))}
      </ul>
    </AdminShell>;
  }

  return <AdminShell username={user.username} current="content">
    <header className="admin-heading">
      <p><Link className="admin-link" href="/admin/content" prefetch={false}>Все материалы</Link></p>
      <h1>{newMaterialLabels[type]}</h1>
      <p className="admin-muted">Материал будет создан как черновик и не появится на сайте, пока вы не смените статус.</p>
    </header>
    <ContentEditorForm mode="create" type={type} />
  </AdminShell>;
}
