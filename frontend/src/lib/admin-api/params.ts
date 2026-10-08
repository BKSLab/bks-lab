import type { AdminMetric, AdminPeriod, ContentStatus, ContentType } from "./types";

export type AdminSearchParams = Record<string, string | string[] | undefined>;

export function firstParam(value: string | string[] | undefined): string {
  return Array.isArray(value) ? (value[0] ?? "") : (value ?? "");
}

export function adminPage(value: string | string[] | undefined): number {
  const raw = firstParam(value);
  const page = /^\d+$/.test(raw) ? Number(raw) : 1;
  return Number.isSafeInteger(page) && page >= 1 && page <= 2147483647 ? page : 1;
}

export function adminPeriod(value: string | string[] | undefined): AdminPeriod {
  const period = firstParam(value);
  return period === "7d" || period === "90d" ? period : "30d";
}

export function adminMetric(value: string | string[] | undefined): AdminMetric {
  return firstParam(value) === "uniques" ? "uniques" : "views";
}

export function adminContentType(value: string | string[] | undefined): ContentType | "" {
  const type = firstParam(value);
  return type === "article" || type === "note" || type === "project" ? type : "";
}

export function adminContentStatus(value: string | string[] | undefined): ContentStatus | "" {
  const status = firstParam(value);
  return status === "active" || status === "draft" || status === "archived" ? status : "";
}

export function adminHref(path: string, params: Record<string, string | number>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "") query.set(key, String(value));
  }
  const encoded = query.toString();
  return encoded ? `${path}?${encoded}` : path;
}

export const contentTypeLabels: Record<ContentType, string> = {
  article: "Статья",
  note: "Заметка",
  project: "Проект",
};

export const contentStatusLabels: Record<ContentStatus, string> = {
  active: "Опубликован",
  draft: "Черновик",
  archived: "В архиве",
};

export function adminNumber(value: number): string {
  return new Intl.NumberFormat("ru-RU").format(value);
}

export function adminDate(value: string | null, withTime = false): string {
  if (!value) return "Не указана";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Не указана";
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone: "UTC",
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    ...(withTime ? { hour: "2-digit", minute: "2-digit" } as const : {}),
  }).format(date);
}
