import { adminDate } from "@/lib/admin-api/params";
import { formatLabels, scoreLabels } from "@/lib/news-api/params";
import type { NewsAnalysis } from "@/lib/news-api/types";

export function NewsAnalysisView({ analysis, detailed = false }: { analysis: NewsAnalysis; detailed?: boolean }) {
  return <div className="news-stack">
    <div className="news-badges">
      <span className="admin-status">{analysis.is_relevant ? "Подходит тематике" : "Вне тематики"}</span>
      {analysis.needs_verification && <span className="admin-status">Нужна проверка фактов</span>}
      {analysis.category_name && <span className="admin-muted">{analysis.category_name}</span>}
    </div>
    <p>{analysis.summary_ru}</p>
    <p className="admin-muted"><strong>Редакционный комментарий:</strong> {analysis.editorial_comment_ru}</p>
    <dl className="news-scores"><div><dt>Для статьи</dt><dd>{analysis.article_score.toFixed(1)}<small> / 100</small></dd></div><div><dt>Короткая новость</dt><dd>{analysis.news_score.toFixed(1)}<small> / 100</small></dd></div></dl>
    {analysis.topics.length > 0 && <p className="admin-muted">Темы: {analysis.topics.map(topic => topic.name).join(", ")}</p>}
    {detailed && <>
      <p>Назначение: {analysis.recommended_formats.map(format => formatLabels[format]).join(", ") || "Не рекомендовано"}.</p>
      <dl className="admin-details">{Object.entries(scoreLabels).map(([key, label]) => <div className="news-detail-row" key={key}><dt>{label}</dt><dd>{analysis.scores[key as keyof typeof analysis.scores]} / 100</dd></div>)}
        <dt>Уверенность модели</dt><dd>{Math.round(analysis.confidence * 100)}%</dd>
        <dt>Модель и версия запроса</dt><dd>{analysis.model} · {analysis.prompt_version}</dd>
        <dt>Дата анализа</dt><dd>{adminDate(analysis.created_at, true)} UTC</dd>
      </dl>
      {analysis.suggested_topics.length > 0 && <p className="admin-muted">Предложенные темы: {analysis.suggested_topics.join(", ")}. Их можно добавить в справочник после редакторской проверки.</p>}
    </>}
  </div>;
}
