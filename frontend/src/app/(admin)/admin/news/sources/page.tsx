import type { Metadata } from "next";
import Link from "next/link";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsSourceToggle } from "@/components/admin/news/NewsSourceToggle";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate } from "@/lib/admin-api/params";
import { externalNewsUrl } from "@/lib/news-api/params";
import type { NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Источники редакционного центра" };

export default async function NewsSourcesPage() {
  const user = await requireAdmin();
  const sources = await adminFetch<NewsSource[]>("/news/sources");
  return <NewsShell username={user.username} current="sources" title="Источники публикаций" description="RSS, Atom и открытые HTML-страницы. Каждый источник проходит проверку перед добавлением.">
    <div><Link className="admin-button admin-button-primary" prefetch={false} href="/admin/news/sources/new">Добавить источник</Link></div>
    {sources.length ? <table className="admin-table admin-card-table" role="table"><caption>Источников: {sources.length}. Время обходов — UTC.</caption>
      <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Источник</th><th scope="col" role="columnheader">Состояние</th><th scope="col" role="columnheader">Последний обход</th><th scope="col" role="columnheader">Управление</th></tr></thead>
      <tbody role="rowgroup">{sources.map(source => <tr role="row" key={source.id}>
        <th scope="row" role="rowheader" className="admin-cell-title"><Link href={`/admin/news/sources/${source.id}`} prefetch={false}>{source.name}</Link><span className="admin-type">{source.kind === "rss" ? "RSS / Atom" : "HTML"} · Каждые {source.interval_hours} ч</span><a href={externalNewsUrl(source.url)} target="_blank" rel="noopener noreferrer" className="news-source-url">{source.url}<span className="sr-only"> (в новой вкладке)</span></a></th>
        <td role="cell" data-label="Состояние"><span className="admin-status">{!source.active ? "На паузе" : source.last_error ? "Ошибка обхода" : source.last_success_at ? "Работает" : "Ожидает первого обхода"}</span>{source.vendor_affiliated && <small>Связан с поставщиком</small>}{source.last_error && <p className="admin-error">{source.last_error}</p>}</td>
        <td role="cell" data-label="Последний успешный обход">{source.last_success_at ? adminDate(source.last_success_at, true) : "Ещё не было"}<small>Новых материалов: {source.last_new_count}</small></td>
        <td role="cell" data-label="Управление"><NewsSourceToggle source={source} /></td>
      </tr>)}</tbody>
    </table> : <p className="admin-empty">Источников пока нет. Добавьте свой URL или выберите адрес из каталога в форме добавления.</p>}
  </NewsShell>;
}
