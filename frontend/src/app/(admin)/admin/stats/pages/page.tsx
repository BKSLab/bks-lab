import type { Metadata } from "next";

import { AdminPeriodFilter } from "@/components/admin/AdminFilters";
import { AdminPagination } from "@/components/admin/AdminPagination";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminNumber, adminPage, adminPeriod, type AdminSearchParams } from "@/lib/admin-api/params";
import type { AdminPaged, PageStat } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Статистика страниц" };

export default async function AdminPagesPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const page = adminPage(params.page);
  const period = adminPeriod(params.period);
  const data = await adminFetch<AdminPaged<PageStat>>(`/stats/pages?period=${period}&page=${page}&page_size=20`);

  return <AdminShell username={user.username} current="pages">
    <header className="admin-heading"><h1>Статистика страниц</h1><p className="admin-muted">Просмотры и посетители за выбранный период, по убыванию просмотров. Даты — UTC.</p></header>
    <section className="admin-section" aria-label="Данные по страницам">
      <AdminPeriodFilter action="/admin/stats/pages" period={period} />
      {data.items.length ? <table className="admin-table admin-card-table" role="table">
        <caption>Страницы и заметки за {period.slice(0, -1)} дней</caption>
        <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Страница</th><th scope="col" role="columnheader">Просмотры</th><th scope="col" role="columnheader">Посетители</th></tr></thead>
        <tbody role="rowgroup">{data.items.map((item) => <tr role="row" key={`${item.path}:${item.note_slug ?? ""}`}>
          <th role="rowheader" scope="row" className="admin-cell-title">{item.path}{item.note_slug && <span className="admin-type">Заметка: {item.note_slug}</span>}</th>
          <td role="cell" data-label="Просмотры" className="admin-numeric">{adminNumber(item.views)}</td>
          <td role="cell" data-label="Посетители" className="admin-numeric">{adminNumber(item.uniques)}</td>
        </tr>)}</tbody>
      </table> : <p className="admin-empty">На этой странице результатов нет. Измените период или вернитесь на первую страницу.</p>}
      <AdminPagination path="/admin/stats/pages" {...data} params={{ period }} />
    </section>
  </AdminShell>;
}
