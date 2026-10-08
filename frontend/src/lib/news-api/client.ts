export class NewsRequestError extends Error {
  constructor(readonly status: number | null, message: string) {
    super(message);
    this.name = "NewsRequestError";
  }
}

export async function newsRequest<T>(path: string, options: { method?: "POST" | "PATCH"; body?: unknown; signal?: AbortSignal } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api/admin/news${path}`, {
      method: options.method ?? "GET",
      credentials: "same-origin",
      cache: "no-store",
      redirect: "error",
      headers: options.body === undefined ? { Accept: "application/json" } : { Accept: "application/json", "Content-Type": "application/json" },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: options.signal ? AbortSignal.any([options.signal, AbortSignal.timeout(15000)]) : AbortSignal.timeout(15000),
    });
  } catch {
    throw new NewsRequestError(null, "Нет связи с сервером. Проверьте подключение и повторите действие.");
  }
  if (!response.ok) {
    const messages: Record<number, string> = {
      401: "Сессия завершилась. Войдите в панель снова.",
      403: "Действие отклонено. Обновите страницу и попробуйте снова.",
      404: "Запись не найдена. Возможно, она уже недоступна.",
      409: "Данные изменились или проверка источника устарела. Обновите страницу и повторите проверку.",
      422: "Проверьте заполненные поля. Для источника нужна успешная проверка текущего адреса и настроек.",
      429: "Слишком много запросов. Подождите немного и повторите действие.",
    };
    throw new NewsRequestError(response.status, messages[response.status] ?? "Сервис временно недоступен. Попробуйте ещё раз позже.");
  }
  try { return await response.json() as T; }
  catch { throw new NewsRequestError(null, "Не удалось прочитать ответ сервера. Обновите страницу."); }
}
