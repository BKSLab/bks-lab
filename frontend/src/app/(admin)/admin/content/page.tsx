import type { Metadata } from "next";
import Link from "next/link";

import { AdminPagination } from "@/components/admin/AdminPagination";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminContentStatus, adminContentType, adminDate, adminHref, adminNumber, adminPage, contentStatusLabels, contentTypeLabels, firstParam, type AdminSearchParams } from "@/lib/admin-api/params";
import type { AdminContentItem, AdminPaged } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Материалы" };

export default async function AdminContentPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const page = adminPage(params.page);
  const type = adminContentType(params.type);
  const status = adminContentStatus(params.status);
  const q = firstParam(params.q).trim().slice(0, 100);
  const filters = { type, status, q };
  const data = await adminFetch<AdminPaged<AdminContentItem>>(adminHref("/content", { ...filters, page, page_size: 20 }));

  return <AdminShell username={user.username} current="content">
    <header className="admin-heading"><h1>Материалы</h1><p className="admin-muted">Статьи, заметки и проекты, включая черновики. Здесь доступен только просмотр; тексты редактируются в Markdown-файлах проекта.</p></header>
    <section className="admin-section" aria-label="Список материалов">
      <form action="/admin/content" method="get" className="admin-filters">
        <div className="admin-field"><label htmlFor="admin-content-type">Тип</label><select name="type" id="admin-content-type" defaultValue={type}>
          <option value="">Все типы</option><option value="article">Статьи</option><option value="note">Заметки</option><option value="project">Проекты</option>
        </select></div>
        <div className="admin-field"><label htmlFor="admin-content-status">Статус</label><select name="status" id="admin-content-status" defaultValue={status}>
          <option value="">Все статусы</option><option value="active">Опубликованы</option><option value="draft">Черновики</option><option value="archived">В архиве</option>
        </select></div>
        <div className="admin-field admin-field-search"><label htmlFor="admin-content-q">Поиск по заголовку</label><input type="search" name="q" id="admin-content-q" defaultValue={q} maxLength={100} /></div>
        <button type="submit" className="admin-button">Найти</button>
        {(type || status || q) && <Link href="/admin/content" prefetch={false} className="admin-button">Сбросить</Link>}
      </form>
      {data.items.length ? <table className="admin-table admin-card-table" role="table">
        <caption>Найдено материалов: {adminNumber(data.total)}</caption>
        <thead role="rowgroup"><tr role="row"><th role="columnheader" scope="col">Материал</th><th role="columnheader" scope="col">Статус</th><th role="columnheader" scope="col">Дата</th><th role="columnheader" scope="col">Просмотры за 30 дней</th></tr></thead>
        <tbody role="rowgroup">{data.items.map((item) => <tr role="row" key={item.id}>
          <th role="rowheader" scope="row" className="admin-cell-title"><Link prefetch={false} href={`/admin/content/${item.id}`}>{item.title}</Link><span className="admin-type">{contentTypeLabels[item.type]}</span></th>
          <td role="cell" data-label="Статус"><span className="admin-status">{contentStatusLabels[item.status]}</span></td>
          <td role="cell" data-label="Дата">{item.published_at ? <time dateTime={item.published_at}>{adminDate(item.published_at)}</time> : "Не указана"}</td>
          <td role="cell" data-label="Просмотры за 30 дней" className="admin-numeric">{adminNumber(item.views_30d)}</td>
        </tr>)}</tbody>
      </table> : <p className="admin-empty">Материалы не найдены. Измените фильтры или поисковый запрос.</p>}
      <AdminPagination path="/admin/content" {...data} params={filters} />
    </section>
  </AdminShell>;
}
