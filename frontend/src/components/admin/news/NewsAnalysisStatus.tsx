import Link from "next/link";
import type { NewsAnalysisState, NewsItem } from "@/lib/news-api/types";

const labels: Record<NewsAnalysisState, string> = {
  analyzed: "Анализ готов",
  queued: "В очереди на анализ",
  running: "Анализируется",
  failed: "Ошибка анализа",
  insufficient_text: "Недостаточно текста",
  pending: "Ожидает постановки в очередь",
};

export function NewsAnalysisStatus({ item }: { item: NewsItem }) {
  const state = item.analysis_state ?? (item.analysis ? "analyzed" : "pending");
  return <div className="news-stack">
    <p><span className="admin-status">{labels[state]}</span></p>
    {state === "pending" && <p className="admin-muted">Задание анализа не создано. Анализ можно запустить вручную на странице материала.</p>}
    {state === "failed" && <>
      <p className="admin-error">{item.analysis_error || "Не удалось выполнить анализ."}</p>
      <p className="admin-muted">После устранения причины ошибки повторите анализ на странице материала.</p>
    </>}
    {state === "insufficient_text" && <p className="admin-muted">Для анализа нужен сохранённый текст. Сначала повторно соберите источник. <Link className="admin-link" prefetch={false} href={`/admin/news/sources/${item.source_id}`}>Открыть источник для повторного сбора</Link>.</p>}
    {item.collection_warning && <p className="admin-muted">Сбор материала: {item.collection_warning}</p>}
    {item.analysis && state !== "analyzed" && <p className="admin-muted">Ниже показан предыдущий анализ материала.</p>}
  </div>;
}
