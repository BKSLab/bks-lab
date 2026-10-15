import { firstParam, type AdminSearchParams } from "@/lib/admin-api/params";
import type { NewsDecisionValue, NewsFormat, NewsJob, NewsJobStatus, NewsRunOutcome, NewsScores } from "./types";

export const formatLabels: Record<NewsFormat, string> = {
  longread_candidate: "Для статьи",
  short_news_candidate: "Короткая новость",
};
export const decisionLabels: Record<NewsDecisionValue, string> = {
  in_work: "В плане публикаций", deferred: "Отложено", rejected: "Отклонено",
};
export const jobStatusLabels: Record<NewsJobStatus, string> = {
  queued: "В очереди", running: "Выполняется", completed: "Завершено", failed: "Ошибка", cancelled: "Отменено",
};
export const jobKindLabels: Record<NewsJob["kind"], string> = {
  collect: "Сбор материалов", discover: "Проверка источника", analyze: "Анализ материала",
};
export const runOutcomeLabels: Record<NewsRunOutcome, string> = {
  new: "Новый", updated: "Обновлён", unchanged: "Без изменений", skipped: "Пропущен",
};

export function newsJobTitle(job: NewsJob): string {
  return `${jobKindLabels[job.kind]}${job.source_name ? ` · ${job.source_name}` : job.kind === "collect" ? " · Все активные источники" : ""}`;
}

export function newsSlug(value: string | string[] | undefined): string {
  const raw = firstParam(value);
  return raw.length <= 240 && /[a-z]/.test(raw) && /^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(raw) ? raw : "";
}

export function newsRunFilters(params: AdminSearchParams): Record<string, string> {
  const outcome = firstParam(params.outcome);
  return {
    source_slug: newsSlug(params.source_slug),
    outcome: Object.hasOwn(runOutcomeLabels, outcome) ? outcome : "",
    warnings_only: firstParam(params.warnings_only) === "true" ? "true" : "",
  };
}

export function newsDuration(start: string | null, end: string | null): string {
  if (!start) return "Ещё не начато";
  if (!end) return "Выполняется";
  const seconds = Math.max(0, Math.round((Date.parse(end) - Date.parse(start)) / 1000));
  if (!Number.isFinite(seconds)) return "Не указана";
  const minutes = Math.floor(seconds / 60);
  return minutes ? `${minutes} мин ${seconds % 60} с` : `${seconds} с`;
}
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
    source_slug: newsSlug(params.source_slug), category_id: newsId(params.category_id), topic_id: newsId(params.topic_id),
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
