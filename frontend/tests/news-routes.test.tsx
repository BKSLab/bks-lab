import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("@/lib/admin-api", () => ({ adminFetch: vi.fn(), requireAdmin: vi.fn() }));
vi.mock("@/components/admin/AdminSessionRefresh", () => ({ AdminSessionRefresh: () => null }));
const { router } = vi.hoisted(() => ({ router: { replace: vi.fn(), push: vi.fn(), refresh: vi.fn() } }));
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  notFound: () => { throw new Error("NOT_FOUND"); },
  redirect: (path: string) => { throw new Error(`REDIRECT:${path}`); },
}));

import AdminLayout from "@/app/(admin)/layout";
import NewsPage from "@/app/(admin)/admin/news/page";
import NewsItemsPage from "@/app/(admin)/admin/news/items/page";
import NewsPlanPage from "@/app/(admin)/admin/news/plan/page";
import NewsItemPage from "@/app/(admin)/admin/news/items/[id]/page";
import NewsSourcesPage from "@/app/(admin)/admin/news/sources/page";
import NewsTopicsPage from "@/app/(admin)/admin/news/topics/page";
import NewsSettingsPage from "@/app/(admin)/admin/news/settings/page";
import NewsRunsPage from "@/app/(admin)/admin/news/runs/page";
import NewsJobPage from "@/app/(admin)/admin/news/jobs/[slug]/page";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { newsAnalysis, newsCategory, newsCollectionStatus, newsDecision, newsItem, newsJob, newsSettings, newsSource, newsTopic } from "./news-fixtures";

const paged = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };
const emptyParams = () => ({ searchParams: Promise.resolve({}) });

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => new Response(JSON.stringify(newsCollectionStatus))));
  vi.mocked(adminFetch).mockReset();
  vi.mocked(requireAdmin).mockReset().mockResolvedValue({ username: "owner" });
  vi.mocked(adminFetch).mockImplementation(async path => {
    if (path === "/news/sources") return [newsSource];
    if (path === "/news/collection-status") return newsCollectionStatus;
    if (path === "/news/topics") return [newsTopic];
    if (path === "/news/categories") return [newsCategory];
    if (path === "/news/items/4") return newsItem;
    if (path === `/news/jobs/${newsJob.slug}`) return newsJob;
    if (path === `/news/sources/${newsSource.slug}`) return newsSource;
    if (path === "/news/settings") return newsSettings;
    return paged;
  });
});
afterEach(() => { vi.unstubAllGlobals(); });

describe("protected editorial routes", () => {
  it.each([
    ["entry", () => NewsPage()],
    ["items", () => NewsItemsPage(emptyParams())],
    ["publication plan", () => NewsPlanPage(emptyParams())],
    ["item", () => NewsItemPage({ params: Promise.resolve({ id: "4" }) })],
    ["sources", () => NewsSourcesPage()],
    ["topics", () => NewsTopicsPage()],
    ["settings", () => NewsSettingsPage()],
    ["runs", () => NewsRunsPage(emptyParams())],
    ["job", () => NewsJobPage({ params: Promise.resolve({ slug: newsJob.slug }), ...emptyParams() })],
  ])("checks the session before reading %s data", async (_label, page) => {
    vi.mocked(requireAdmin).mockRejectedValue(new Error("LOGIN_REQUIRED"));
    await expect(page()).rejects.toThrow("LOGIN_REQUIRED");
    expect(adminFetch).not.toHaveBeenCalled();
  });

  it("opens the collection from the editorial center link", async () => {
    await expect(NewsPage()).rejects.toThrow("REDIRECT:/admin/news/items");
  });

  it("loads only prepared sources and keeps management on one accessible screen", async () => {
    const { container } = render(<AdminLayout>{await NewsSourcesPage()}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/news/sources");
    expect(adminFetch).toHaveBeenCalledWith("/news/collection-status");
    expect(screen.getByRole("rowheader").textContent).toContain(newsSource.name);
    expect(screen.getByText(newsSource.description)).toBeTruthy();
    expect(screen.getByRole("switch", { name: `Регулярная проверка: ${newsSource.name}` }).getAttribute("aria-checked")).toBe("false");
    expect(screen.getByText("Ежедневно · 08:00, 20:00")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Проверить все включённые" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "История проверок" }).getAttribute("href")).toBe("/admin/news/runs");
    expect(screen.queryByRole("link", { name: "Каталог" })).toBeNull();
    expect(container.querySelector('[href*="sources/new"], [href*="sources/catalogue"]')).toBeNull();
    expect(container.textContent).not.toMatch(/RSS|Atom|HTML|CSS|Приоритет|Доверие|поставщик/);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect((await axe(container)).violations).toEqual([]);
  });

  it("keeps an empty prepared catalogue empty without manual connection actions", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path === "/news/collection-status" ? newsCollectionStatus : []);
    render(<AdminLayout>{await NewsSourcesPage()}</AdminLayout>);
    expect(screen.getByText("Готовых источников пока нет.")).toBeTruthy();
    expect(screen.queryByRole("switch")).toBeNull();
    expect(screen.queryByRole("button", { name: /Проверить/ })).toBeNull();
    expect(adminFetch).toHaveBeenCalledWith("/news/sources");
  });

  it.each([
    ["all active sources", "Проверить все включённые", {}],
    ["one paused source", `Проверить: ${newsSource.name}`, { source_slug: newsSource.slug }],
  ])("starts a manual check of %s directly from the sources page", async (_label, button, body) => {
    vi.mocked(adminFetch).mockImplementation(async path => path === "/news/sources" ? [{ ...newsSource, active: true }] : newsCollectionStatus);
    const fetchMock = vi.fn().mockImplementation(async (_path: string, options: RequestInit) => new Response(JSON.stringify(options.method === "POST" ? { job_slug: newsJob.slug } : newsCollectionStatus), { status: options.method === "POST" ? 202 : 200 }));
    vi.stubGlobal("fetch", fetchMock);
    try {
      render(<AdminLayout>{await NewsSourcesPage()}</AdminLayout>);
      fireEvent.click(screen.getByRole("button", { name: button }));
      await screen.findByRole("link", { name: "Открыть отчёт" });
      const call = fetchMock.mock.calls.find(([, options]) => options.method === "POST")!;
      expect(call[0]).toBe("/api/admin/news/jobs/collect");
      expect(JSON.parse(call[1].body)).toEqual(body);
    } finally { vi.unstubAllGlobals(); }
  });

  it("renders accessible collection filters, two format choices, and the empty state", async () => {
    const { container } = render(<AdminLayout>{await NewsItemsPage({ searchParams: Promise.resolve({ format: "longread_candidate", source_slug: newsSource.slug, page: "-1", min_score: "800" }) })}</AdminLayout>);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByRole("link", { name: "Для статей" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: "Короткие новости" }).getAttribute("href")).toContain("format=short_news_candidate");
    expect(screen.getByRole("link", { name: "Перейти к основному содержимому" }).getAttribute("href")).toBe("#main-content");
    expect(screen.getByRole("link", { name: "Перейти к запускам" })).toBeTruthy();
    const request = vi.mocked(adminFetch).mock.calls.find(([path]) => path.startsWith("/news/items?"))![0];
    expect(request).toContain("page=1");
    expect(request).not.toContain("min_score");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("guides an empty installation to prepared sources", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path.startsWith("/news/items?") ? paged : []);
    render(<AdminLayout>{await NewsItemsPage(emptyParams())}</AdminLayout>);
    expect(screen.getByRole("link", { name: "Открыть источники" }).getAttribute("href")).toBe("/admin/news/sources");
  });

  it("keeps the publication plan inside the editorial navigation", async () => {
    const { container } = render(<AdminLayout>{await NewsPlanPage(emptyParams())}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/news/items?decision=in_work&page=1&page_size=20");
    expect(screen.getByText(/План пока пуст/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Выбрать материалы из подборок" }).getAttribute("href")).toBe("/admin/news/items");
    const panelNavigation = within(screen.getByRole("navigation", { name: "Разделы панели" }));
    expect(panelNavigation.queryByRole("link", { name: "План публикаций" })).toBeNull();
    expect(panelNavigation.getByRole("link", { name: "Редакционный центр" }).getAttribute("aria-current")).toBe("page");
    const editorialNavigation = within(screen.getByRole("navigation", { name: "Редакционный центр" }));
    expect(editorialNavigation.getByRole("link", { name: "План публикаций" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect((await axe(container)).violations).toEqual([]);
  });

  it("renders a publication list with the saved summary, source, ratings, format and notes", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, items: [{ ...newsItem, decision: newsDecision }], total: 1 });
    const { container } = render(<AdminLayout>{await NewsPlanPage(emptyParams())}</AdminLayout>);
    const list = screen.getByRole("list", { name: "План публикаций" });
    expect(list.tagName).toBe("UL");
    const entries = within(list).getAllByRole("listitem");
    expect(entries).toHaveLength(1);
    expect(entries[0].parentElement).toBe(list);
    const row = within(within(entries[0]).getByRole("article", { name: newsItem.title }));
    expect(row.getByText(newsAnalysis.summary_ru)).toBeTruthy();
    expect(row.getByText(newsAnalysis.editorial_comment_ru, { exact: false })).toBeTruthy();
    expect(row.getByText(newsDecision.comment, { selector: "p" })).toBeTruthy();
    expect(row.getByText(`${newsItem.source_name} · 08.10.2026`)).toBeTruthy();
    expect(row.getByText("Анализ готов")).toBeTruthy();
    expect(row.getByText("Для статьи", { selector: "dt" }).nextElementSibling?.textContent).toContain("86.0");
    expect(row.getByText("Короткая новость", { selector: "dt" }).nextElementSibling?.textContent).toContain("82.0");
    expect(row.getByText("Назначение в плане:").parentElement?.textContent).toContain("Короткая новость");
    expect(row.getByRole("link", { name: /^Первоисточник/ }).getAttribute("href")).toBe(newsItem.url);
    expect(row.getByRole("link", { name: newsItem.title }).getAttribute("href")).toBe("/admin/news/items/4");
    expect(row.queryByRole("button", { name: "Добавить в план" })).toBeNull();
    expect(row.getByRole("button", { name: "Убрать из плана" })).toBeTruthy();
    fireEvent.click(row.getByText("Редакторское решение", { selector: "summary" }));
    expect(row.getByRole("button", { name: "Сохранить изменения в плане" })).toBeTruthy();
    expect(row.getByRole("button", { name: "Отклонить" })).toBeTruthy();
    expect((row.getByLabelText("Комментарий редактора") as HTMLTextAreaElement).value).toBe(newsDecision.comment);
    expect((await axe(container)).violations).toEqual([]);
  });

  it("renders news as list rows without losing full analysis, excerpt or editorial actions", async () => {
    const summary = "Полная выжимка исследования. ".repeat(12);
    vi.mocked(adminFetch).mockImplementation(async path => path.startsWith("/news/items?") ? {
      ...paged, total: 2, items: [
        { ...newsItem, analysis: { ...newsAnalysis, summary_ru: summary }, duplicate_of_id: 3 },
        { ...newsItem, id: 5, title: "Материал без анализа", analysis: null, analysis_state: "failed", analysis_error: "Модель временно недоступна.", collection_warning: "Текст получен не полностью." },
      ],
    } : []);
    const { container } = render(<AdminLayout>{await NewsItemsPage(emptyParams())}</AdminLayout>);
    const list = screen.getByRole("list", { name: "Подобранные новости" });
    expect(list.tagName).toBe("UL");
    const entries = within(list).getAllByRole("listitem");
    expect(entries).toHaveLength(2);
    expect(entries.every(entry => entry.tagName === "LI" && entry.parentElement === list)).toBe(true);
    const row = within(within(entries[0]).getByRole("article", { name: newsItem.title }));
    expect(row.getByText(summary.trim()).textContent).toBe(summary);
    expect(row.getByText(newsAnalysis.editorial_comment_ru, { exact: false })).toBeTruthy();
    expect(row.getByText(`${newsItem.source_name} · 08.10.2026`)).toBeTruthy();
    expect(row.getByText("Для статьи", { selector: "dt" }).nextElementSibling?.textContent).toContain("86.0");
    expect(row.getByText("Короткая новость", { selector: "dt" }).nextElementSibling?.textContent).toContain("82.0");
    for (const label of ["Анализ готов", "Подходит тематике", "Нужна проверка фактов", "Исследования", "Темы: AI Engineering"]) expect(row.getByText(label)).toBeTruthy();
    expect(row.getByRole("link", { name: "другим сохранённым материалом" }).getAttribute("href")).toBe("/admin/news/items/3");
    expect(row.getByRole("button", { name: "Добавить в план" })).toBeTruthy();
    fireEvent.click(row.getByText("Редакторское решение", { selector: "summary" }));
    expect(row.getByRole("button", { name: "Отложить" })).toBeTruthy();
    expect(row.getByRole("button", { name: "Отклонить" })).toBeTruthy();
    expect(row.getByLabelText("Назначение")).toBeTruthy();
    expect(row.getByLabelText("Комментарий редактора")).toBeTruthy();
    const pendingRow = within(entries[1]);
    expect(pendingRow.getByText(newsItem.excerpt)).toBeTruthy();
    expect(pendingRow.getByText("Ошибка анализа")).toBeTruthy();
    expect(pendingRow.getByText("Модель временно недоступна.")).toBeTruthy();
    expect(pendingRow.getByText("Сбор материала: Текст получен не полностью.")).toBeTruthy();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("keeps pagination scoped to the plan and ignores conflicting collection filters", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, total: 41, page: 2, pages: 3 });
    render(<AdminLayout>{await NewsPlanPage({ searchParams: Promise.resolve({ page: "2", decision: "rejected", format: "longread_candidate" }) })}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/news/items?decision=in_work&page=2&page_size=20");
    expect(screen.getByRole("link", { name: "Назад" }).getAttribute("href")).toBe("/admin/news/plan?page=1");
    expect(screen.getByRole("link", { name: "Вперёд" }).getAttribute("href")).toBe("/admin/news/plan?page=3");
  });

  it("offers a return to the first plan page after its last item is removed", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, page: 2 });
    render(<AdminLayout>{await NewsPlanPage({ searchParams: Promise.resolve({ page: "2" }) })}</AdminLayout>);
    expect(screen.getByRole("link", { name: "На первую" }).getAttribute("href")).toBe("/admin/news/plan?page=1");
  });

  it("includes the entire selected final UTC day in date filtering", async () => {
    await NewsItemsPage({ searchParams: Promise.resolve({ date_from: "2026-10-01", date_to: "2026-10-08" }) });
    const request = vi.mocked(adminFetch).mock.calls.find(([path]) => path.startsWith("/news/items?"))![0];
    const params = new URLSearchParams(request.split("?")[1]);
    expect(params.get("date_from")).toBe("2026-10-01T00:00:00Z");
    expect(params.get("date_to")).toBe("2026-10-08T23:59:59.999999Z");
  });

  it("keeps invalid reversed dates editable without sending a failing API query", async () => {
    render(<AdminLayout>{await NewsItemsPage({ searchParams: Promise.resolve({ date_from: "2026-10-08", date_to: "2026-10-01" }) })}</AdminLayout>);
    expect(screen.getByRole("alert").textContent).toContain("Начало периода");
    expect(screen.getByLabelText("Найден начиная с").getAttribute("aria-invalid")).toBe("true");
    expect(vi.mocked(adminFetch).mock.calls.some(([path]) => path.startsWith("/news/items?"))).toBe(false);
  });

  it.each([
    ["pending", "Ожидает постановки в очередь"],
    ["queued", "В очереди на анализ"],
    ["running", "Анализируется"],
    ["failed", "Ошибка анализа"],
    ["insufficient_text", "Недостаточно текста"],
  ])("shows the actual %s analysis state on the collection row", async (state, label) => {
    vi.mocked(adminFetch).mockImplementation(async path => path.startsWith("/news/items?") ? { ...paged, items: [{ ...newsItem, analysis: null, status: "pending_analysis", analysis_state: state }], total: 1 } : []);
    render(<AdminLayout>{await NewsItemsPage(emptyParams())}</AdminLayout>);
    expect(screen.getByText(label, { selector: "span" })).toBeTruthy();
    expect(screen.queryByText("Ожидает анализа")).toBeNull();
    expect(screen.getByRole("option", { name: "Без анализа" }).getAttribute("value")).toBe("pending_analysis");
    expect(screen.getByRole("link", { name: newsItem.title }).getAttribute("href")).toBe("/admin/news/items/4");
  });

  it.each([
    ["pending", "Ожидает постановки в очередь"],
    ["queued", "В очереди на анализ"],
    ["running", "Анализируется"],
  ])("shows the %s analysis state on the material page", async (state, label) => {
    vi.mocked(adminFetch).mockResolvedValue({ ...newsItem, analysis: null, status: "pending_analysis", analysis_state: state, analysis_history: [] });
    render(<AdminLayout>{await NewsItemPage({ params: Promise.resolve({ id: "4" }) })}</AdminLayout>);
    expect(screen.getByText(label)).toBeTruthy();
    expect(screen.queryByText(/Материал ожидает анализа/)).toBeNull();
  });

  it("shows a failed analysis reason and allows retry without promising background work", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...newsItem, analysis: null, status: "pending_analysis", analysis_state: "failed", analysis_error: "Модель временно недоступна.", analysis_history: [] });
    const { container } = render(<AdminLayout>{await NewsItemPage({ params: Promise.resolve({ id: "4" }) })}</AdminLayout>);
    expect(screen.getByText("Ошибка анализа")).toBeTruthy();
    expect(screen.getByText("Модель временно недоступна.")).toBeTruthy();
    expect(screen.queryByText(/ожидает анализа|Ожидает постановки|В очереди на анализ/)).toBeNull();
    expect((screen.getByRole("button", { name: "Повторить анализ" }) as HTMLButtonElement).disabled).toBe(false);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect((await axe(container)).violations).toEqual([]);
  });

  it("guides a material with insufficient text to collection and hides analysis retry", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...newsItem, analysis: null, content: null, excerpt: "", status: "pending_analysis", analysis_state: "insufficient_text", collection_warning: "Не удалось загрузить страницу.", analysis_history: [] });
    const { container } = render(<AdminLayout>{await NewsItemPage({ params: Promise.resolve({ id: "4" }) })}</AdminLayout>);
    expect(screen.getByText("Недостаточно текста")).toBeTruthy();
    expect(screen.getByText("Сбор материала: Не удалось загрузить страницу.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Открыть источник для повторного сбора" }).getAttribute("href")).toBe(`/admin/news/sources#${newsSource.slug}`);
    expect(screen.queryByRole("button", { name: "Повторить анализ" })).toBeNull();
    expect(screen.queryByText(/Материал ожидает анализа/)).toBeNull();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("keeps a failed reanalysis visible alongside its previous result and escapes the reason", async () => {
    const reason = '<img src=x onerror="alert(1)">';
    vi.mocked(adminFetch).mockResolvedValue({ ...newsItem, analysis_state: "failed", analysis_error: reason });
    const { container } = render(<AdminLayout>{await NewsItemPage({ params: Promise.resolve({ id: "4" }) })}</AdminLayout>);
    expect(screen.getByText("Ошибка анализа")).toBeTruthy();
    expect(screen.getByText(reason)).toBeTruthy();
    expect(container.querySelector("img[src=x]")).toBeNull();
    expect(screen.getByText("Ниже показан предыдущий анализ материала.")).toBeTruthy();
    expect(screen.getAllByText(newsAnalysis.summary_ru)).toHaveLength(2);
  });

  it("escapes source text, guards external URLs, and shows analysis and decision history", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...newsItem, url: "javascript:alert(1)", content: '<img src=x onerror="alert(1)">', analysis: newsAnalysis });
    const { container } = render(<AdminLayout>{await NewsItemPage({ params: Promise.resolve({ id: "4" }) })}</AdminLayout>);
    expect(container.querySelector('[href^="javascript:"]')).toBeNull();
    expect(container.querySelector("img[src=x]")).toBeNull();
    expect(screen.getByText('<img src=x onerror="alert(1)">')).toBeTruthy();
    expect(screen.getAllByText("Нужна проверка фактов").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Повторить анализ" })).toBeTruthy();
    expect((await axe(container)).violations).toEqual([]);
  });

  it.each([
    ["sources", () => NewsSourcesPage()],
    ["taxonomy", () => NewsTopicsPage()],
    ["settings", () => NewsSettingsPage()],
    ["runs", () => NewsRunsPage(emptyParams())],
    ["job", () => NewsJobPage({ params: Promise.resolve({ slug: newsJob.slug }), ...emptyParams() })],
  ])("renders %s with one main, one heading and no axe violations", async (_label, page) => {
    const { container } = render(<AdminLayout>{await page()}</AdminLayout>);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect((await axe(container)).violations).toEqual([]);
  });
});
