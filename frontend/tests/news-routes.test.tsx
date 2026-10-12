import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
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
import NewsItemPage from "@/app/(admin)/admin/news/items/[id]/page";
import NewsSourcesPage from "@/app/(admin)/admin/news/sources/page";
import NewsCataloguePage from "@/app/(admin)/admin/news/sources/catalogue/page";
import NewsNewSourcePage from "@/app/(admin)/admin/news/sources/new/page";
import NewsSourcePage from "@/app/(admin)/admin/news/sources/[id]/page";
import NewsTopicsPage from "@/app/(admin)/admin/news/topics/page";
import NewsSettingsPage from "@/app/(admin)/admin/news/settings/page";
import NewsRunsPage from "@/app/(admin)/admin/news/runs/page";
import NewsJobPage from "@/app/(admin)/admin/news/jobs/[id]/page";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { sourceCatalogue } from "./news-catalogue-fixtures";
import { newsAnalysis, newsCategory, newsItem, newsJob, newsSettings, newsSource, newsTopic } from "./news-fixtures";

const paged = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };
const emptyParams = () => ({ searchParams: Promise.resolve({}) });

beforeEach(() => {
  vi.mocked(adminFetch).mockReset();
  vi.mocked(requireAdmin).mockReset().mockResolvedValue({ username: "owner" });
  vi.mocked(adminFetch).mockImplementation(async path => {
    if (path === "/news/sources") return [newsSource];
    if (path === "/news/sources/catalogue") return sourceCatalogue;
    if (path === "/news/topics") return [newsTopic];
    if (path === "/news/categories") return [newsCategory];
    if (path === "/news/items/4") return newsItem;
    if (path === "/news/jobs/9") return newsJob;
    if (path === "/news/settings") return newsSettings;
    return paged;
  });
});

describe("protected editorial routes", () => {
  it("loads catalogue suggestions from the protected API", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path === "/news/sources/catalogue"
      ? [{ ...sourceCatalogue[0], name: "Каталог из БД" }] : []);
    render(<AdminLayout>{await NewsCataloguePage()}</AdminLayout>);
    expect(screen.getByRole("heading", { name: /^Каталог из БД/ })).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("1 из 1");
    expect(adminFetch).toHaveBeenCalledWith("/news/sources/catalogue");
  });

  it.each([
    ["entry", () => NewsPage()],
    ["items", () => NewsItemsPage(emptyParams())],
    ["item", () => NewsItemPage({ params: Promise.resolve({ id: "4" }) })],
    ["sources", () => NewsSourcesPage()],
    ["source catalogue", () => NewsCataloguePage()],
    ["new source", () => NewsNewSourcePage(emptyParams())],
    ["source", () => NewsSourcePage({ params: Promise.resolve({ id: "7" }) })],
    ["topics", () => NewsTopicsPage()],
    ["settings", () => NewsSettingsPage()],
    ["runs", () => NewsRunsPage(emptyParams())],
    ["job", () => NewsJobPage({ params: Promise.resolve({ id: "9" }) })],
  ])("checks the session before reading %s data", async (_label, page) => {
    vi.mocked(requireAdmin).mockRejectedValue(new Error("LOGIN_REQUIRED"));
    await expect(page()).rejects.toThrow("LOGIN_REQUIRED");
    expect(adminFetch).not.toHaveBeenCalled();
  });

  it("opens the collection from the editorial center link", async () => {
    await expect(NewsPage()).rejects.toThrow("REDIRECT:/admin/news/items");
  });

  it("links the complete catalogue from connected sources", async () => {
    render(<AdminLayout>{await NewsSourcesPage()}</AdminLayout>);
    expect(screen.getByRole("link", { name: "Каталог источников (98)" }).getAttribute("href")).toBe("/admin/news/sources/catalogue");
  });

  it.each([
    ["all active sources", "", {}],
    ["one paused source", "7", { source_id: 7 }],
  ])("starts a manual check of %s directly from the sources page", async (_label, selected, body) => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ job_id: 9, status: "queued" }), { status: 202 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ ...newsJob, kind: "collect", progress: { sources_done: 1, new_count: 2 }, result: {} })));
    vi.stubGlobal("fetch", fetchMock);
    try {
      render(<AdminLayout>{await NewsSourcesPage()}</AdminLayout>);
      const controls = within(screen.getByRole("region", { name: "Ручная проверка публикаций" }));
      expect(fetchMock).not.toHaveBeenCalled();
      fireEvent.change(controls.getByLabelText("Источник для сбора"), { target: { value: selected } });
      fireEvent.click(controls.getByRole("button", { name: "Проверить сейчас" }));
      await controls.findByText("Новых");
      expect(fetchMock).toHaveBeenCalledTimes(2);
      expect(fetchMock.mock.calls[0][0]).toBe("/api/admin/news/jobs/collect");
      expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: "POST", credentials: "same-origin", cache: "no-store" });
      expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual(body);
      expect(fetchMock.mock.calls[1][0]).toBe("/api/admin/news/jobs/9");
      expect(controls.getByRole("link", { name: "Открыть задание № 9" }).getAttribute("href")).toBe("/admin/news/jobs/9");
      expect(controls.getByRole("link", { name: "История проверок" }).getAttribute("href")).toBe("/admin/news/runs");
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("does not offer a manual collection before any source is connected", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path === "/news/sources/catalogue" ? sourceCatalogue : []);
    render(<AdminLayout>{await NewsSourcesPage()}</AdminLayout>);
    expect(screen.queryByRole("button", { name: "Проверить сейчас" })).toBeNull();
    expect(screen.getByText(/Подключённых источников пока нет/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Каталог источников (98)" })).toBeTruthy();
  });

  it("prefills a source selected in the catalogue by its stable ID", async () => {
    render(<AdminLayout>{await NewsNewSourcePage({ searchParams: Promise.resolve({ catalogue: "eng-simon" }) })}</AdminLayout>);
    expect((screen.getByLabelText("Название (обязательно)") as HTMLInputElement).value).toBe("Simon Willison");
    expect((screen.getByLabelText("URL источника (обязательно)") as HTMLInputElement).value).toBe("https://simonwillison.net/atom/entries/");
    expect((screen.getByLabelText("Способ получения") as HTMLSelectElement).value).toBe("rss");
  });

  it.each(["missing-id", "tools-crossref", "authors-hinton"])("keeps unsupported catalogue ID %s out of the source form", async catalogue => {
    render(<AdminLayout>{await NewsNewSourcePage({ searchParams: Promise.resolve({ catalogue }) })}</AdminLayout>);
    expect(screen.getByText(/Этот пункт каталога недоступен для подключения/).getAttribute("role")).toBe("status");
    expect((screen.getByLabelText("URL источника (обязательно)") as HTMLInputElement).value).toBe("");
  });

  it("renders accessible collection filters, two format choices, and the empty state", async () => {
    const { container } = render(<AdminLayout>{await NewsItemsPage({ searchParams: Promise.resolve({ format: "longread_candidate", source_id: "7", page: "-1", min_score: "800" }) })}</AdminLayout>);
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

  it("guides an empty installation to source discovery", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path.startsWith("/news/items?") ? paged : []);
    render(<AdminLayout>{await NewsItemsPage(emptyParams())}</AdminLayout>);
    expect(screen.getByRole("link", { name: "Добавить источник" }).getAttribute("href")).toBe("/admin/news/sources/new");
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

  it("renders pending items without assuming analysis exists", async () => {
    vi.mocked(adminFetch).mockImplementation(async path => path.startsWith("/news/items?") ? { ...paged, items: [{ ...newsItem, analysis: null, status: "pending_analysis" }], total: 1 } : []);
    render(<AdminLayout>{await NewsItemsPage(emptyParams())}</AdminLayout>);
    expect(screen.getByText("Ожидает анализа", { selector: "span" })).toBeTruthy();
    expect(screen.getByRole("link", { name: newsItem.title }).getAttribute("href")).toBe("/admin/news/items/4");
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
    ["source catalogue", () => NewsCataloguePage()],
    ["new source", () => NewsNewSourcePage(emptyParams())],
    ["source settings", () => NewsSourcePage({ params: Promise.resolve({ id: "7" }) })],
    ["taxonomy", () => NewsTopicsPage()],
    ["settings", () => NewsSettingsPage()],
    ["runs", () => NewsRunsPage(emptyParams())],
    ["job", () => NewsJobPage({ params: Promise.resolve({ id: "9" }) })],
  ])("renders %s with one main, one heading and no axe violations", async (_label, page) => {
    const { container } = render(<AdminLayout>{await page()}</AdminLayout>);
    expect(screen.getAllByRole("main")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect((await axe(container)).violations).toEqual([]);
  });
});
