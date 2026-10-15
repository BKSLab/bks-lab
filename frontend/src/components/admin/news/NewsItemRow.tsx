import Link from "next/link";
import { adminDate } from "@/lib/admin-api/params";
import { externalNewsUrl, formatLabels } from "@/lib/news-api/params";
import type { NewsFormat, NewsItem } from "@/lib/news-api/types";
import { NewsAnalysisView } from "./NewsAnalysisView";
import { NewsAnalysisStatus } from "./NewsAnalysisStatus";
import { NewsDecisionForm } from "./NewsDecisionForm";

export function NewsItemRow({ item, format, planned = false }: { item: NewsItem; format?: NewsFormat; planned?: boolean }) {
  return <article className="news-item-row" aria-labelledby={`news-item-${item.id}`}>
    <div className="news-item-content news-stack">
      <header className="news-stack"><p className="news-item-meta">{item.source_name} · {adminDate(item.published_at)}{item.published_at ? "" : " (дата публикации)"}</p>
        <h2 id={`news-item-${item.id}`}><Link className="admin-link" prefetch={false} href={`/admin/news/items/${item.id}`}>{item.title}</Link></h2>
        <a className="admin-link news-original" href={externalNewsUrl(item.url)} target="_blank" rel="noopener noreferrer">Первоисточник<span className="sr-only">: {item.title} (в новой вкладке)</span></a>
      </header>
      <NewsAnalysisStatus item={item} />
      {item.analysis ? <NewsAnalysisView analysis={item.analysis} /> : item.excerpt && <p>{item.excerpt}</p>}
      {item.duplicate_of_id && <p className="admin-muted">Совпадает с <Link className="admin-link" prefetch={false} href={`/admin/news/items/${item.duplicate_of_id}`}>другим сохранённым материалом</Link>.</p>}
    </div>
    <div className="news-item-actions news-stack">
      {planned && item.decision && <div className="news-stack">
        <p><strong>Назначение в плане:</strong> {formatLabels[item.decision.format]}</p>
        {item.decision.comment && <p><strong>Комментарий редактора:</strong> {item.decision.comment}</p>}
      </div>}
      <NewsDecisionForm itemId={item.id} itemTitle={item.title} current={item.decision} defaultFormat={format ?? item.analysis?.recommended_formats[0]} compact />
    </div>
  </article>;
}
