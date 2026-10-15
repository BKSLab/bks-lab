import type { Metadata } from "next";
import Link from "next/link";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { NewsSourceToggle } from "@/components/admin/news/NewsSourceToggle";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate } from "@/lib/admin-api/params";
import { externalNewsUrl } from "@/lib/news-api/params";
import type { SourceCatalogueEntry } from "@/lib/news-api/catalogue";
import type { NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Источники редакционного центра" };

export default async function NewsSourcesPage() {
  const user = await requireAdmin();
  const [sources, sourceCatalogue] = await Promise.all([
    adminFetch<NewsSource[]>("/news/sources"),
    adminFetch<SourceCatalogueEntry[]>("/news/sources/catalogue"),
  ]);
  return <NewsShell username={user.username} current="sources" title="Источники публикаций" description="RSS, Atom и открытые HTML-страницы. Каждый источник проходит проверку перед добавлением.">
    <div className="news-actions"><Link className="admin-button admin-button-primary" prefetch={false} href="/admin/news/sources/catalogue">Каталог источников ({sourceCatalogue.length})</Link><Link className="admin-button" prefetch={false} href="/admin/news/sources/new">Добавить источник</Link></div>
    {sources.length > 0 && <section className="admin-section news-stack" aria-labelledby="news-sources-check">
      <h2 id="news-sources-check">Ручная проверка публикаций</h2>
      <p className="admin-muted">Соберите новые материалы сейчас, не дожидаясь расписания. Выберите один источник или все включённые. Ход и результат проверки появятся здесь.</p>
      <NewsJobLauncher sources={sources} />
      <Link className="admin-link" prefetch={false} href="/admin/news/runs">История проверок</Link>
    </section>}
    {sources.length ? <table className="admin-table admin-card-table" role="table"><caption>Источников: {sources.length}. Время обходов — UTC.</caption>
      <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader">Источник</th><th scope="col" role="columnheader">Состояние</th><th scope="col" role="columnheader">Последний обход</th><th scope="col" role="columnheader">Управление</th></tr></thead>
      <tbody role="rowgroup">{sources.map(source => <tr role="row" key={source.id}>
        <th scope="row" role="rowheader" className="admin-cell-title"><Link href={`/admin/news/sources/${source.slug}`} prefetch={false}>{source.name}</Link><span className="admin-type">{source.kind === "rss" ? "RSS / Atom" : "HTML"} · Каждые {source.interval_hours} ч</span><a href={externalNewsUrl(source.url)} target="_blank" rel="noopener noreferrer" className="news-source-url">{source.url}<span className="sr-only"> (в новой вкладке)</span></a></th>
        <td role="cell" data-label="Состояние"><span className="admin-status">{!source.active ? "На паузе" : source.health === "degraded" ? "Есть предупреждения" : source.last_error ? "Ошибка обхода" : source.last_success_at ? "Работает" : "Ожидает первого обхода"}</span>{source.vendor_affiliated && <small>Связан с поставщиком</small>}{source.last_error && <p className={source.health === "degraded" ? "admin-muted" : "admin-error"}>{source.last_error}</p>}</td>
        <td role="cell" data-label="Последний успешный обход">{source.last_success_at ? adminDate(source.last_success_at, true) : "Ещё не было"}<small>Новых материалов: {source.last_new_count}</small></td>
        <td role="cell" data-label="Управление"><NewsSourceToggle source={source} /></td>
      </tr>)}</tbody>
    </table> : <p className="admin-empty">Подключённых источников пока нет. Выберите из полного каталога или добавьте свой URL.</p>}
  </NewsShell>;
}
