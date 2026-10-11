import type { AdminContentImage, ContentImageSection } from "./types";

export class ContentRequestError extends Error {
  constructor(readonly status: number | null, message: string) {
    super(message);
    this.name = "ContentRequestError";
  }
}

const errorMessages: Record<number, string> = {
  401: "Сессия завершилась. Войдите в панель снова.",
  403: "Действие отклонено. Обновите страницу и попробуйте снова.",
  404: "Материал не найден. Возможно, он уже удалён.",
  409: "Такой адрес (slug) уже занят в этом типе материалов. Выберите другой.",
  422: "Проверьте заполненные поля: не хватает обязательных данных или они заполнены некорректно.",
  429: "Слишком много запросов. Подождите немного и повторите действие.",
};

/** Browser-side client for admin content mutations. Cookie session and exact Origin are enforced by the server. */
export async function contentRequest<T>(path: string, options: { method?: "GET" | "POST" | "PATCH" | "DELETE"; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/admin/content${path}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: options.body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
    });
  } catch {
    throw new ContentRequestError(null, "Нет связи с сервером. Проверьте подключение и повторите действие.");
  }
  if (!response.ok) {
    throw new ContentRequestError(response.status, errorMessages[response.status] ?? "Сервис временно недоступен. Попробуйте ещё раз позже.");
  }
  if (response.status === 204) return undefined as T;
  try {
    return await response.json() as T;
  } catch {
    throw new ContentRequestError(null, "Не удалось прочитать ответ сервера. Обновите страницу.");
  }
}

export function renderMarkdownPreview(contentMarkdown: string, signal?: AbortSignal): Promise<{ html: string }> {
  return contentRequest<{ html: string }>("/preview", { method: "POST", body: { content_markdown: contentMarkdown }, signal });
}

export function listContentImages(signal?: AbortSignal): Promise<AdminContentImage[]> {
  return contentRequest<AdminContentImage[]>("/images", { signal });
}

/** Multipart upload: Content-Type is left to the browser so it sets the boundary. */
export async function uploadContentImage(file: File, section?: ContentImageSection, signal?: AbortSignal): Promise<AdminContentImage> {
  const formData = new FormData();
  formData.append("file", file);
  if (section) formData.append("section", section);
  let response: Response;
  try {
    response = await fetch("/api/admin/content/images", {
      method: "POST",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: { Accept: "application/json" },
      body: formData,
      signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
    });
  } catch {
    throw new ContentRequestError(null, "Нет связи с сервером. Проверьте подключение и повторите действие.");
  }
  if (!response.ok) {
    throw new ContentRequestError(response.status, errorMessages[response.status] ?? "Сервис временно недоступен. Попробуйте ещё раз позже.");
  }
  try {
    return await response.json() as AdminContentImage;
  } catch {
    throw new ContentRequestError(null, "Не удалось прочитать ответ сервера. Обновите страницу.");
  }
}
