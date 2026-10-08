import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { NewsAnalysisView } from "@/components/admin/news/NewsAnalysisView";
import { NewsDecisionForm } from "@/components/admin/news/NewsDecisionForm";
import { NewsJobLauncher } from "@/components/admin/news/NewsJobLauncher";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminDate } from "@/lib/admin-api/params";
import { decisionLabels, externalNewsUrl, formatLabels, newsId } from "@/lib/news-api/params";
import type { NewsItemDetail } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Разбор материала" };

export default async function NewsItemPage({ params }: { params: Promise<{ id: string }> }) {
  const user = await requireAdmin();
  const id = newsId((await params).id);
  if (!id) notFound();
  const item = await adminFetch<NewsItemDetail>(`/news/items/${id}`);
  return <NewsShell username={user.username} current="items" title={item.title}>
    <div className="news-actions"><Link className="admin-link" prefetch={false} href="/admin/news/items">К подборкам</Link><a className="admin-link" href={externalNewsUrl(item.url)} target="_blank" rel="noopener noreferrer">Открыть первоисточник<span className="sr-only"> (в новой вкладке)</span></a></div>
    <dl className="admin-details"><dt>Источник</dt><dd><Link className="admin-link" prefetch={false} href={`/admin/news/sources/${item.source_id}`}>{item.source_name}</Link></dd><dt>Дата публикации</dt><dd>{adminDate(item.published_at, true)}{item.published_at && " UTC"}</dd><dt>Впервые найден</dt><dd>{adminDate(item.first_seen_at, true)} UTC</dd><dt>Последний обход</dt><dd>{adminDate(item.last_seen_at, true)} UTC</dd></dl>
    {item.duplicate_of_id && <p className="admin-muted">Совпадает с <Link className="admin-link" prefetch={false} href={`/admin/news/items/${item.duplicate_of_id}`}>материалом № {item.duplicate_of_id}</Link>.</p>}
    <section className="admin-section news-stack" aria-labelledby="news-analysis-heading"><h2 id="news-analysis-heading">Редакционный анализ</h2>
      {item.analysis ? <NewsAnalysisView analysis={item.analysis} detailed /> : <p className="admin-empty">Материал ожидает анализа. Его можно запустить вручную после подключения модели.</p>}
      <NewsJobLauncher itemId={item.id} />
    </section>
    <section className="admin-section news-stack" aria-labelledby="news-decision-heading"><h2 id="news-decision-heading">Решение редактора</h2><NewsDecisionForm itemId={item.id} current={item.decision} /></section>
    <section className="admin-section news-stack" aria-labelledby="news-text-heading"><h2 id="news-text-heading">Сохранённый текст</h2><p className="news-source-text">{item.content || item.excerpt || "Текст недоступен или удалён по сроку хранения. Откройте первоисточник."}</p></section>
    <section className="admin-section news-stack" aria-labelledby="news-history-heading"><h2 id="news-history-heading">История</h2>
      <details><summary>Анализы: {item.analysis_history.length}</summary><div className="news-stack">{item.analysis_history.length ? item.analysis_history.map(analysis => <section className="news-history-entry" key={analysis.id}><h3>{adminDate(analysis.created_at, true)} UTC · {analysis.model}</h3><NewsAnalysisView analysis={analysis} detailed /></section>) : <p>Анализов пока нет.</p>}</div></details>
      <details><summary>Редакторские решения: {item.decision_history.length}</summary>{item.decision_history.length ? <ol className="news-history">{item.decision_history.map(decision => <li key={decision.id}><p><strong>{decisionLabels[decision.decision]}</strong> · {formatLabels[decision.format]}</p><p className="admin-muted">{adminDate(decision.created_at, true)} UTC · {decision.editor}</p>{decision.comment && <p className="news-source-text">{decision.comment}</p>}</li>)}</ol> : <p>Решений пока нет.</p>}</details>
    </section>
  </NewsShell>;
}
