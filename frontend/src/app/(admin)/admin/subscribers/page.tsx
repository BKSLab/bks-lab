import type { Metadata } from "next";

import { AdminPagination } from "@/components/admin/AdminPagination";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate, adminNumber, adminPage, type AdminSearchParams } from "@/lib/admin-api/params";
import type { AdminPaged, AdminSubscriber } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Подписчики" };

export default async function AdminSubscribersPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const page = adminPage(params.page);
  const data = await adminFetch<AdminPaged<AdminSubscriber>>(`/subscribers?page=${page}&page_size=20`);

  return <AdminShell username={user.username} current="subscribers">
    <header className="admin-heading"><h1>Подписчики</h1><p className="admin-muted">Адреса подписавшихся на обновления, начиная с самых новых. Даты — UTC.</p></header>
    <section className="admin-section" aria-label="Список подписчиков">
      {data.items.length ? <table className="admin-table admin-card-table" role="table">
        <caption>Всего подписчиков: {adminNumber(data.total)}</caption>
        <thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col">Электронная почта</th><th role="columnheader" scope="col">Дата подписки, UTC</th></tr></thead>
        <tbody role="rowgroup">{data.items.map((item) => <tr role="row" key={item.email}>
          <th role="rowheader" scope="row" className="admin-cell-title">{item.email}</th>
          <td role="cell" data-label="Подписка"><time dateTime={item.subscribed_at}>{adminDate(item.subscribed_at, true)}</time></td>
        </tr>)}</tbody>
      </table> : <p className="admin-empty">На этой странице подписчиков нет.</p>}
      <AdminPagination path="/admin/subscribers" {...data} />
    </section>
  </AdminShell>;
}
