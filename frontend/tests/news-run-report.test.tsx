import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

const { router, fetchMock } = vi.hoisted(() => ({ router: { replace: vi.fn(), push: vi.fn(), refresh: vi.fn() }, fetchMock: vi.fn() }));
vi.mock("next/navigation", () => ({ useRouter: () => router, notFound: () => { throw new Error("NOT_FOUND"); } }));
vi.mock("@/lib/admin-api", () => ({ adminFetch: vi.fn(), requireAdmin: vi.fn() }));
vi.mock("@/components/admin/AdminSessionRefresh", () => ({ AdminSessionRefresh: () => null }));

import AdminLayout from "@/app/(admin)/layout";
import NewsJobPage from "@/app/(admin)/admin/news/jobs/[slug]/page";
import NewsSourcePage from "@/app/(admin)/admin/news/sources/[slug]/page";
import NewsRunsPage from "@/app/(admin)/admin/news/runs/page";
import { NewsRunReport } from "@/components/admin/news/NewsRunReport";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { newsDuration, newsRunFilters, newsSlug } from "@/lib/news-api/params";
import type { NewsPaged, NewsRunItem } from "@/lib/news-api/types";
import { newsCollectJob, newsJob, newsRun, newsRunItem, newsSource } from "./news-fixtures";

const paged = <T,>(items: T[], extra: Partial<NewsPaged<T>> = {}): NewsPaged<T> => ({ items, total: items.length, page: 1, page_size: 20, ...extra });
const filters = { source_slug: "", outcome: "", warnings_only: "" };
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });

beforeEach(() => {
  fetchMock.mockReset();
  Object.values(router).forEach(fn => fn.mockReset());
  vi.stubGlobal("fetch", fetchMock);
  vi.mocked(requireAdmin).mockResolvedValue({ username: "owner" });
  vi.mocked(adminFetch).mockReset().mockImplementation(async path => {
    if (path === `/news/jobs/${newsCollectJob.slug}`) return newsCollectJob;
    if (path.startsWith(`/news/jobs/${newsCollectJob.slug}/runs?`)) return paged([newsRun]);
    if (path.startsWith(`/news/jobs/${newsCollectJob.slug}/items?`)) return paged([newsRunItem]);
    if (path.startsWith("/news/runs?")) return paged([newsRun]);
    if (path === "/news/sources") return [newsSource];
    if (path === `/news/sources/${newsSource.slug}`) return newsSource;
    return [];
  });
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

function report(items: NewsRunItem[] = [newsRunItem], runs = [newsRun]) {
  return <NewsRunReport initialJob={newsCollectJob} initialRuns={paged(runs)} initialItems={paged(items)} sources={[newsSource]} filters={filters} />;
}

describe("collection run report", () => {
  it("extends the existing slug job route with source checks, material links and UTC times", async () => {
    const { container } = render(<AdminLayout>{await NewsJobPage({ params: Promise.resolve({ slug: newsCollectJob.slug }), searchParams: Promise.resolve({}) })}</AdminLayout>);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Сбор материалов · Все активные источники");
    expect(screen.getByRole("region", { name: "Обходы источников" })).toBeTruthy();
    expect(screen.getByRole("link", { name: newsRunItem.title }).getAttribute("href")).toBe(`/admin/news/items/${newsRunItem.item_id}`);
    expect(screen.getByRole("link", { name: /^Открыть задание анализа/ }).getAttribute("href")).toBe(`/admin/news/jobs/${newsRunItem.analysis_job_slug}`);
    expect(screen.getAllByText("Начало (UTC)")).toHaveLength(2);
    expect(screen.getAllByText("2 мин 29 с")).toHaveLength(2);
    expect(screen.getByText(/статус анализа относятся к версии/)).toBeTruthy();
    expect(container.textContent).not.toContain("№");
    expect(container.querySelector('[href="/admin/news/sources/7"]')).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect((await axe(container)).violations).toEqual([]);
  });

  it("shows all outcomes, skipped entry diagnostics and preservation of the previous version", async () => {
    const items: NewsRunItem[] = [
      newsRunItem,
      { ...newsRunItem, id: 22, title: "Обновлённая публикация", outcome: "updated", analysis_status: "pending", analysis_job_slug: null },
      { ...newsRunItem, id: 23, title: "Прежняя публикация", outcome: "unchanged", reason: "Не удалось обновить текст.", warning: "Страница временно недоступна.", stage: "fetch", preserved_previous: true, analysis_status: null, analysis_job_slug: null },
      { ...newsRunItem, id: 24, title: "Слишком старая публикация", item_id: null, outcome: "skipped", reason: "Дата публикации раньше границы сбора.", stage: "filter", analysis_status: null, analysis_job_slug: null },
    ];
    const { container } = render(report(items));
    const rows = within(screen.getByRole("list", { name: "Материалы запуска" }));
    for (const label of ["Новый", "Обновлён", "Без изменений", "Пропущен"]) expect(rows.getByText(label)).toBeTruthy();
    expect(rows.getByText("Сохранена предыдущая версия материала.")).toBeTruthy();
    expect(rows.getByText("Предупреждение: Страница временно недоступна.")).toBeTruthy();
    expect(rows.getByText("Этап: Загрузка страницы")).toBeTruthy();
    expect(rows.getByText("Этап: Фильтрация")).toBeTruthy();
    expect(rows.getByText("Анализ: Ожидает постановки в очередь.")).toBeTruthy();
    expect(rows.queryByRole("link", { name: "Слишком старая публикация" })).toBeNull();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("allows only known collection parameters and keeps diagnostics as escaped text", () => {
    const markup = '<img src=x onerror="alert(1)">';
    const { container } = render(report([{ ...newsRunItem, title: markup, url: "javascript:alert(1)", warning: markup }], [{ ...newsRun, error: markup, parameters: { ...newsRun.parameters, arbitrary_field: "private-value" } }]));
    fireEvent.click(screen.getByText("Параметры обхода"));
    for (const label of ["Публикации начиная с (UTC)", "Лимит материалов", "Лимит текста, символов", "Условный HTTP-запрос"]) expect(screen.getByText(label)).toBeTruthy();
    expect(screen.getByText("08.09.2026, 08:00")).toBeTruthy();
    expect(screen.getByText("Вручную")).toBeTruthy();
    expect(container.textContent).not.toContain("private-value");
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector('[href^="javascript:"]')).toBeNull();
    expect(screen.getAllByText(markup).length).toBeGreaterThan(0);
  });

  it("explains an HTTP 304 without inventing material observations", () => {
    render(report([], [{ ...newsRun, not_modified: true, http_status: 304, new_count: 0, unchanged_count: 0, warning_count: 0 }]));
    expect(screen.getByText(/Список публикаций повторно не передавался/)).toBeTruthy();
    expect(screen.getByText("HTTP 304")).toBeTruthy();
    expect(screen.getByText("Материалов по этим фильтрам пока нет.")).toBeTruthy();
    expect(screen.queryByRole("list", { name: "Материалы запуска" })).toBeNull();
  });

  it("states collection limits and diagnostic truncation explicitly", () => {
    render(report([], [{ ...newsRun, limit_reached: true, diagnostics_truncated: true }]));
    expect(screen.getByText(/Остальные публикации не проверялись/)).toBeTruthy();
    expect(screen.getByText(/Часть диагностических записей не сохранена/)).toBeTruthy();
    expect(screen.getByText(/число пропусков может быть неполным/)).toBeTruthy();
  });

  it("distinguishes skipped analysis from a completed analysis of the observed version", () => {
    render(report([{ ...newsRunItem, analysis_status: "skipped", analysis_reason: "Версия материала изменилась до начала анализа." }]));
    expect(screen.getByText("Анализ: Анализ пропущен.")).toBeTruthy();
    expect(screen.getByText("Версия материала изменилась до начала анализа.")).toBeTruthy();
    expect(screen.queryByText("Анализ: Анализ готов.")).toBeNull();
  });

  it("keeps two independent pagination controls and filters in their links", () => {
    const selected = { source_slug: newsSource.slug, outcome: "skipped", warnings_only: "true" };
    render(<NewsRunReport initialJob={newsCollectJob} initialRuns={paged([newsRun], { page: 2, total: 45, pages: 3 })} initialItems={paged([newsRunItem], { page: 3, total: 100, pages: 5 })} sources={[newsSource]} filters={selected} />);
    const sourcePages = within(screen.getByRole("navigation", { name: "Страницы обходов источников" }));
    const materialPages = within(screen.getByRole("navigation", { name: "Страницы материалов запуска" }));
    const sourceParams = new URL(sourcePages.getByRole("link", { name: "Вперёд" }).getAttribute("href")!, "https://example.org").searchParams;
    const materialParams = new URL(materialPages.getByRole("link", { name: "Вперёд" }).getAttribute("href")!, "https://example.org").searchParams;
    expect(sourceParams.get("runs_page")).toBe("3");
    expect(sourceParams.get("page")).toBe("3");
    expect(materialParams.get("runs_page")).toBe("2");
    expect(materialParams.get("page")).toBe("4");
    for (const params of [sourceParams, materialParams]) {
      expect(params.get("source_slug")).toBe(newsSource.slug);
      expect(params.get("outcome")).toBe("skipped");
      expect(params.get("warnings_only")).toBe("true");
      expect(params.has("source_id")).toBe(false);
    }
    expect((screen.getByLabelText("Источник") as HTMLSelectElement).value).toBe(newsSource.slug);
    expect((screen.getByLabelText("Только с предупреждениями") as HTMLInputElement).checked).toBe(true);
    expect(screen.getByRole("button", { name: "Применить" }).closest("form")?.getAttribute("method")).toBe("get");
  });

  it("requests paged observations with validated source, outcome and warning filters", async () => {
    await NewsJobPage({ params: Promise.resolve({ slug: newsCollectJob.slug }), searchParams: Promise.resolve({ source_slug: newsSource.slug, outcome: "skipped", warnings_only: "true", page: "3", runs_page: "2" }) });
    expect(adminFetch).toHaveBeenCalledWith(`/news/jobs/${newsCollectJob.slug}/runs?page=2&page_size=20`);
    expect(adminFetch).toHaveBeenCalledWith(`/news/jobs/${newsCollectJob.slug}/items?source_slug=${newsSource.slug}&outcome=skipped&warnings_only=true&page=3&page_size=20`);
  });

  it("shows source settings and history links using stable slugs", async () => {
    const source = await NewsSourcePage({ params: Promise.resolve({ slug: newsSource.slug }) });
    expect(adminFetch).toHaveBeenCalledWith(`/news/sources/${newsSource.slug}`);
    expect(source).toBeTruthy();
    render(<AdminLayout>{await NewsRunsPage({ searchParams: Promise.resolve({ source_slug: newsSource.slug }) })}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith(`/news/runs?source_slug=${newsSource.slug}&page=1&page_size=20`);
    expect(screen.getByRole("link", { name: /^Отчёт сбора/ }).getAttribute("href")).toBe(`/admin/news/jobs/${newsCollectJob.slug}`);
    expect(screen.getByRole("link", { name: newsSource.name }).getAttribute("href")).toBe(`/admin/news/sources/${newsSource.slug}`);
  });

  it.each(["9", "0", "../jobs", "two/slugs", "", "bad_slug"])("rejects an invalid slug %s without a numeric fallback", async slug => {
    await expect(NewsJobPage({ params: Promise.resolve({ slug }), searchParams: Promise.resolve({}) })).rejects.toThrow("NOT_FOUND");
    await expect(NewsSourcePage({ params: Promise.resolve({ slug }) })).rejects.toThrow("NOT_FOUND");
    expect(adminFetch).not.toHaveBeenCalled();
  });

  it("validates report filters and accepts a digit-leading named slug", () => {
    expect(newsSlug("404-media")).toBe("404-media");
    expect(newsRunFilters({ source_slug: "7", outcome: "secret", warnings_only: "yes" })).toEqual(filters);
    expect(newsDuration(null, null)).toBe("Ещё не начато");
  });

  it("refreshes live collection and version analysis until completion, then stops polling", async () => {
    vi.useFakeTimers();
    fetchMock.mockResolvedValueOnce(json(newsCollectJob)).mockResolvedValueOnce(json(paged([newsRun]))).mockResolvedValueOnce(json(paged([{ ...newsRunItem, analysis_status: "queued" }])))
      .mockResolvedValueOnce(json(newsCollectJob)).mockResolvedValueOnce(json(paged([newsRun]))).mockResolvedValueOnce(json(paged([newsRunItem])));
    render(<NewsRunReport initialJob={{ ...newsCollectJob, status: "running", completed_at: null }} initialRuns={paged([])} initialItems={paged([])} sources={[newsSource]} filters={filters} />);
    await act(async () => {});
    expect(screen.getByText("Анализ: В очереди на анализ.")).toBeTruthy();
    expect(screen.getAllByRole("status").some(status => status.textContent?.includes("Завершено"))).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(screen.getByText("Анализ: Анализ готов.")).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock.mock.calls[0][0]).toBe(`/api/admin/news/jobs/${newsCollectJob.slug}`);
    expect(fetchMock.mock.calls[1][0]).toContain(`/api/admin/news/jobs/${newsCollectJob.slug}/runs?`);
    expect(fetchMock.mock.calls.every(([, options]) => options.cache === "no-store" && options.credentials === "same-origin")).toBe(true);
  });

  it("continues polling a completed parent until running source snapshots settle", async () => {
    vi.useFakeTimers();
    const runningRun = { ...newsRun, status: "running" as const, completed_at: null };
    fetchMock.mockResolvedValueOnce(json(newsCollectJob)).mockResolvedValueOnce(json(paged([runningRun]))).mockResolvedValueOnce(json(paged([newsRunItem])))
      .mockResolvedValueOnce(json(newsCollectJob)).mockResolvedValueOnce(json(paged([newsRun]))).mockResolvedValueOnce(json(paged([newsRunItem])));
    render(<NewsRunReport initialJob={newsCollectJob} initialRuns={paged([runningRun])} initialItems={paged([newsRunItem])} sources={[newsSource]} filters={filters} />);
    await act(async () => {});
    const sourceChecks = within(screen.getByRole("region", { name: "Обходы источников" }));
    expect(sourceChecks.getByText("Выполняется", { selector: "span" })).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(2500); });
    expect(sourceChecks.getByText("Завершено", { selector: "span" })).toBeTruthy();
    await act(async () => { await vi.advanceTimersByTimeAsync(10000); });
    expect(fetchMock).toHaveBeenCalledTimes(6);
  });

  it("preserves the loaded report on refresh failure and retries without creating another job", async () => {
    fetchMock.mockRejectedValueOnce(new TypeError("offline")).mockResolvedValueOnce(json(paged([newsRun]))).mockResolvedValueOnce(json(paged([newsRunItem])))
      .mockResolvedValueOnce(json(newsCollectJob)).mockResolvedValueOnce(json(paged([newsRun]))).mockResolvedValueOnce(json(paged([newsRunItem])));
    render(report());
    fireEvent.click(screen.getByRole("button", { name: "Обновить отчёт" }));
    expect((await screen.findByRole("alert")).textContent).toContain("Нет связи");
    expect(screen.getByRole("link", { name: newsRunItem.title })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Обновить отчёт" }));
    await act(async () => {});
    expect(screen.queryByRole("alert")).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(6);
    expect(fetchMock.mock.calls.every(([, options]) => options.method === "GET")).toBe(true);
  });

  it("keeps discovery on its existing job route without collection-only API calls", async () => {
    vi.mocked(adminFetch).mockResolvedValue(newsJob);
    render(<AdminLayout>{await NewsJobPage({ params: Promise.resolve({ slug: newsJob.slug }), searchParams: Promise.resolve({}) })}</AdminLayout>);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Проверка источника");
    expect(screen.getByRole("region", { name: "Предпросмотр источника" })).toBeTruthy();
    expect(vi.mocked(adminFetch).mock.calls.some(([path]) => path.includes("/runs") || path.includes("/items"))).toBe(false);
  });
});
