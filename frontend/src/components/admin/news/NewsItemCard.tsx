import Link from "next/link";
import { adminDate } from "@/lib/admin-api/params";
import { externalNewsUrl } from "@/lib/news-api/params";
import type { NewsFormat, NewsItem } from "@/lib/news-api/types";
import { NewsAnalysisView } from "./NewsAnalysisView";
import { NewsDecisionForm } from "./NewsDecisionForm";

export function NewsItemCard({ item, format }: { item: NewsItem; format?: NewsFormat }) {
  return <article className="news-item" aria-labelledby={`news-item-${item.id}`}>
    <header className="news-stack"><p className="news-item-meta">{item.source_name} · {adminDate(item.published_at)}{item.published_at ? "" : " (дата публикации)"}</p>
      <h2 id={`news-item-${item.id}`}><Link className="admin-link" prefetch={false} href={`/admin/news/items/${item.id}`}>{item.title}</Link></h2>
      <a className="admin-link news-original" href={externalNewsUrl(item.url)} target="_blank" rel="noopener noreferrer">Первоисточник<span className="sr-only">: {item.title} (в новой вкладке)</span></a>
    </header>
    {item.analysis ? <NewsAnalysisView analysis={item.analysis} /> : <><span className="admin-status">Ожидает анализа</span>{item.excerpt && <p>{item.excerpt}</p>}</>}
    {item.duplicate_of_id && <p className="admin-muted">Совпадает с <Link className="admin-link" prefetch={false} href={`/admin/news/items/${item.duplicate_of_id}`}>материалом № {item.duplicate_of_id}</Link>.</p>}
    <NewsDecisionForm itemId={item.id} current={item.decision} defaultFormat={format} compact />
  </article>;
}
