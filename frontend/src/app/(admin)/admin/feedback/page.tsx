import type { Metadata } from "next";

import { AdminPagination } from "@/components/admin/AdminPagination";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate, adminNumber, adminPage, type AdminSearchParams } from "@/lib/admin-api/params";
import type { AdminFeedback, AdminPaged } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Обратная связь" };

export default async function AdminFeedbackPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const page = adminPage(params.page);
  const data = await adminFetch<AdminPaged<AdminFeedback>>(`/feedback?page=${page}&page_size=20`);

  return <AdminShell username={user.username} current="feedback">
    <header className="admin-heading">
      <h1>Обратная связь</h1>
      <p className="admin-muted">Обращения из формы «Связаться», начиная с самых новых. Даты — UTC.</p>
    </header>
    <section className="admin-section" aria-label="Полученные обращения">
      <p className="admin-muted">Всего обращений: {adminNumber(data.total)}</p>
      {data.items.length ? <ol className="admin-feedback-list" role="list">
        {data.items.map((item) => <li key={item.id}>
          <article className="admin-feedback-message" aria-labelledby={`feedback-${item.id}`}>
            <h2 id={`feedback-${item.id}`}>Сообщение от {item.name}</h2>
            <dl className="admin-feedback-meta">
              <div><dt>Контакт для ответа</dt><dd>{item.email}</dd></div>
              <div><dt>Получено, UTC</dt><dd><time dateTime={item.created_at}>{adminDate(item.created_at, true)}</time></dd></div>
            </dl>
            <p className="admin-feedback-text">{item.message}</p>
          </article>
        </li>)}
      </ol> : <p className="admin-empty">На этой странице обращений нет.</p>}
      <AdminPagination path="/admin/feedback" {...data} />
    </section>
  </AdminShell>;
}
