import type { Metadata } from "next";
import Link from "next/link";
import { AdminPagination } from "@/components/admin/AdminPagination";
import { NewsItemCard } from "@/components/admin/news/NewsItemCard";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminHref, adminPage, type AdminSearchParams } from "@/lib/admin-api/params";
import { decisionLabels, newsFilters } from "@/lib/news-api/params";
import type { NewsFormat, NewsItem, NewsPaged, NewsSource, NewsTaxonomy } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Редакционный центр" };

export default async function NewsItemsPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const filters = newsFilters(params);
  const page = adminPage(params.page);
  const invalidPeriod = !!(filters.date_from && filters.date_to && filters.date_from > filters.date_to);
  const apiFilters = {
    ...filters,
    date_from: filters.date_from ? `${filters.date_from}T00:00:00Z` : "",
    date_to: filters.date_to ? `${filters.date_to}T23:59:59.999999Z` : "",
  };
  const [data, sources, topics, categories] = await Promise.all([
    invalidPeriod ? Promise.resolve<NewsPaged<NewsItem>>({ items: [], total: 0, page, page_size: 20 })
      : adminFetch<NewsPaged<NewsItem>>(adminHref("/news/items", { ...apiFilters, page, page_size: 20 })),
    adminFetch<NewsSource[]>("/news/sources"), adminFetch<NewsTaxonomy[]>("/news/topics"), adminFetch<NewsTaxonomy[]>("/news/categories"),
  ]);
  return <NewsShell username={user.username} current="items" title="Подборки материалов" description="Новые публикации из выбранных источников, оценённые по редакционной политике BKS Lab. Решения остаются за редактором.">
    <nav aria-label="Назначение материалов"><ul className="admin-nav news-format-nav">{[
      ["", "Все материалы"], ["longread_candidate", "Для статей"], ["short_news_candidate", "Короткие новости"],
    ].map(([format, label]) => <li key={format}><Link prefetch={false} href={adminHref("/admin/news/items", { ...filters, format })} aria-current={filters.format === format ? "page" : undefined}>{label}</Link></li>)}</ul></nav>
    <section className="admin-section" aria-label="Фильтры и результаты">
      <form key={JSON.stringify(filters)} action="/admin/news/items" method="get" className="admin-filters news-filters">
        {filters.format && <input type="hidden" name="format" value={filters.format} />}
        {([{ name: "source_id", label: "Источник", items: sources }, { name: "category_id", label: "Рубрика", items: categories }, { name: "topic_id", label: "Тема", items: topics }]).map(field => <div className="admin-field" key={field.name}><label htmlFor={`news-filter-${field.name}`}>{field.label}</label><select id={`news-filter-${field.name}`} name={field.name} defaultValue={filters[field.name]}><option value="">Все</option>{field.items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></div>)}
        <div className="admin-field"><label htmlFor="news-filter-status">Анализ</label><select id="news-filter-status" name="status" defaultValue={filters.status}><option value="">Любой статус</option><option value="pending_analysis">Ожидает анализа</option><option value="analyzed">Проанализирован</option></select></div>
        <div className="admin-field"><label htmlFor="news-filter-decision">Решение</label><select id="news-filter-decision" name="decision" defaultValue={filters.decision}><option value="">Все решения</option>{Object.entries(decisionLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></div>
        <div className="admin-field"><label htmlFor="news-filter-score">Рейтинг от, 0–100</label><input id="news-filter-score" name="min_score" type="number" min={0} max={100} defaultValue={filters.min_score} /></div>
        <div className="admin-field"><label htmlFor="news-date-from">Найден начиная с</label><input id="news-date-from" name="date_from" type="date" defaultValue={filters.date_from} aria-invalid={invalidPeriod || undefined} aria-describedby={invalidPeriod ? "news-period-error" : undefined} /></div>
        <div className="admin-field"><label htmlFor="news-date-to">Найден по включительно</label><input id="news-date-to" name="date_to" type="date" defaultValue={filters.date_to} min={filters.date_from || undefined} aria-invalid={invalidPeriod || undefined} aria-describedby={invalidPeriod ? "news-period-error" : undefined} /></div>
        <button className="admin-button" type="submit">Применить</button><Link className="admin-button" prefetch={false} href="/admin/news/items">Сбросить</Link>
      </form>
      {invalidPeriod && <p id="news-period-error" role="alert" className="admin-error">Начало периода должно быть раньше его окончания или совпадать с ним. Исправьте даты и примените фильтры.</p>}
      <p className="admin-muted">Найдено: {data.total}. Даты указаны в UTC.</p>
      {data.items.length ? <div className="news-items">{data.items.map(item => <NewsItemCard key={`${item.id}-${filters.format}`} item={item} format={filters.format as NewsFormat || undefined} />)}</div>
        : <div className="admin-empty news-stack"><p>{sources.length ? "Материалов по этим фильтрам пока нет. Сбросьте фильтры или запустите сбор." : "Добавьте первый источник и проверьте его, чтобы начать собирать материалы."}</p><Link className="admin-link" prefetch={false} href={sources.length ? "/admin/news/runs" : "/admin/news/sources/new"}>{sources.length ? "Перейти к запускам" : "Добавить источник"}</Link></div>}
      <AdminPagination path="/admin/news/items" page={data.page} total={data.total} pages={data.pages ?? Math.ceil(data.total / data.page_size)} params={filters} />
    </section>
  </NewsShell>;
}
