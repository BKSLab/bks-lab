import { firstParam, type AdminSearchParams } from "@/lib/admin-api/params";
import type { NewsDecisionValue, NewsFormat, NewsJobStatus, NewsScores } from "./types";

export const formatLabels: Record<NewsFormat, string> = {
  longread_candidate: "Для статьи",
  short_news_candidate: "Короткая новость",
};
export const decisionLabels: Record<NewsDecisionValue, string> = {
  in_work: "В работе", deferred: "Отложено", rejected: "Отклонено",
};
export const jobStatusLabels: Record<NewsJobStatus, string> = {
  queued: "В очереди", running: "Выполняется", completed: "Завершено", failed: "Ошибка", cancelled: "Отменено",
};
export const scoreLabels: Record<keyof NewsScores, string> = {
  topical_fit: "Соответствие тематике", significance: "Значимость", freshness: "Свежесть", article_potential: "Потенциал статьи",
};

export function newsId(value: string | string[] | undefined): string {
  const raw = firstParam(value);
  return /^\d+$/.test(raw) && Number.isSafeInteger(Number(raw)) && Number(raw) > 0 ? String(Number(raw)) : "";
}

export function newsFilters(params: AdminSearchParams): Record<string, string> {
  const enumValue = (key: string, values: string[]) => values.includes(firstParam(params[key])) ? firstParam(params[key]) : "";
  const date = (key: string) => {
    const raw = firstParam(params[key]);
    const parsed = Date.parse(raw);
    return /^\d{4}-\d{2}-\d{2}$/.test(raw) && !Number.isNaN(parsed) && new Date(parsed).toISOString().slice(0, 10) === raw ? raw : "";
  };
  const rawScore = firstParam(params.min_score);
  return {
    source_id: newsId(params.source_id), category_id: newsId(params.category_id), topic_id: newsId(params.topic_id),
    format: enumValue("format", Object.keys(formatLabels)),
    status: enumValue("status", ["pending_analysis", "analyzed"]),
    decision: enumValue("decision", Object.keys(decisionLabels)),
    min_score: /^\d{1,3}$/.test(rawScore) && Number(rawScore) <= 100 ? String(Number(rawScore)) : "",
    date_from: date("date_from"), date_to: date("date_to"),
  };
}

export function externalNewsUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    if (!["https:", "http:"].includes(url.protocol) || url.username || url.password) return undefined;
    return url.href;
  } catch { return undefined; }
}
