import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("@/lib/admin-api", () => ({ adminFetch: vi.fn(), requireAdmin: vi.fn() }));
vi.mock("@/components/admin/AdminSessionRefresh", () => ({ AdminSessionRefresh: () => null }));
vi.mock("@/components/admin/AdminChart", () => ({ AdminChart: () => <div data-testid="chart" /> }));
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), refresh: vi.fn() }),
  notFound: () => { throw new Error("NOT_FOUND"); },
}));

import AdminLayout from "@/app/(admin)/layout";
import AdminContentPage from "@/app/(admin)/admin/content/page";
import AdminContentDetailPage from "@/app/(admin)/admin/content/[id]/page";
import AdminOverviewPage from "@/app/(admin)/admin/page";
import AdminPagesPage from "@/app/(admin)/admin/stats/pages/page";
import AdminReferrersPage from "@/app/(admin)/admin/stats/referrers/page";
import AdminSubscribersPage from "@/app/(admin)/admin/subscribers/page";
import AdminFeedbackPage from "@/app/(admin)/admin/feedback/page";
import { adminFetch, requireAdmin } from "@/lib/admin-api";

const item = {
  id: 1, type: "article", slug: "demo", title: "Архитектура API", category: "development",
  tags: ["FastAPI"], published_at: "2026-10-08", status: "draft", word_count: 500, views_30d: 0,
};
const paged = { items: [], total: 0, page: 1, page_size: 20, pages: 0 };
const emptyParams = () => ({ searchParams: Promise.resolve({}) });

beforeEach(() => {
  vi.mocked(adminFetch).mockReset();
  vi.mocked(requireAdmin).mockReset().mockResolvedValue({ username: "owner" });
});

describe("admin server routes", () => {
  it.each([
    ["overview", () => AdminOverviewPage(emptyParams())],
    ["pages", () => AdminPagesPage(emptyParams())],
    ["referrers", () => AdminReferrersPage(emptyParams())],
    ["content", () => AdminContentPage(emptyParams())],
    ["detail", () => AdminContentDetailPage({ params: Promise.resolve({ id: "1" }) })],
    ["subscribers", () => AdminSubscribersPage(emptyParams())],
    ["feedback", () => AdminFeedbackPage(emptyParams())],
  ])("checks the session before loading %s data", async (_name, loadPage) => {
    vi.mocked(requireAdmin).mockRejectedValue(new Error("LOGIN_REQUIRED"));
    await expect(loadPage()).rejects.toThrow("LOGIN_REQUIRED");
    expect(adminFetch).not.toHaveBeenCalled();
  });

  it("renders overview cards and a server-rendered alternative to the chart", async () => {
    vi.mocked(adminFetch).mockImplementation(async (path) => path === "/overview" ? {
      views_today: 4, views_7d: 20, views_30d: 65, uniques_today: 3,
      top_pages_30d: [], top_referrers_30d: [],
    } : [{ date: "2026-10-08", value: 4 }]);
    const { container } = render(<AdminLayout>{await AdminOverviewPage(emptyParams())}</AdminLayout>);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Обзор сайта");
    expect(screen.getByText("Просмотры сегодня")).toBeTruthy();
    expect(screen.getByText("Данные графика в таблице")).toBeTruthy();
    expect(container.querySelector("time")?.getAttribute("datetime")).toBe("2026-10-08");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("preserves filters in pagination and exposes creation and editing links", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, items: [item], total: 45, page: 2, pages: 3 });
    const element = await AdminContentPage({ searchParams: Promise.resolve({ type: "article", status: "draft", q: "API", page: "2" }) });
    const { container } = render(<AdminLayout>{element}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/content?type=article&status=draft&q=API&page=2&page_size=20");
    expect(screen.getByRole("link", { name: "Архитектура API" }).getAttribute("href")).toBe("/admin/content/1");
    expect(screen.getByRole("link", { name: "Вперёд" }).getAttribute("href")).toContain("status=draft&q=API&page=3");
    expect(screen.getByRole("link", { name: "Новая статья" }).getAttribute("href")).toBe("/admin/content/new?type=article");
    expect(screen.getByRole("link", { name: "Править" }).getAttribute("href")).toBe("/admin/content/1/edit");
    expect(screen.queryByText(/Markdown-файлах проекта/)).toBeNull();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("omits links to unpublished drafts and shows editing controls with update time", async () => {
    vi.mocked(adminFetch).mockResolvedValue({
      ...item, excerpt: "Аннотация", cover_image: null, seo_title: null, seo_description: null, og_image: null,
      related_slug: null, featured: false, sort_order: null, reading_time: null, content_markdown: "Текст",
      created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-08T10:00:00Z", views_timeseries_30d: [],
    });
    const { container } = render(<AdminLayout>{await AdminContentDetailPage({ params: Promise.resolve({ id: "1" }) })}</AdminLayout>);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(item.title);
    expect(screen.queryByRole("link", { name: "Открыть на сайте" })).toBeNull();
    expect(screen.getByRole("link", { name: "Править" }).getAttribute("href")).toBe("/admin/content/1/edit");
    expect(screen.getByRole("button", { name: "Удалить материал" })).toBeTruthy();
    expect(screen.getByText("08.10.2026, 10:00")).toBeTruthy();
    expect(screen.getByText("Черновик")).toBeTruthy();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("rejects malformed material ids after authentication", async () => {
    await expect(AdminContentDetailPage({ params: Promise.resolve({ id: "../overview" }) })).rejects.toThrow("NOT_FOUND");
    expect(requireAdmin).toHaveBeenCalledOnce();
    expect(adminFetch).not.toHaveBeenCalled();
  });

  it("shows subscribers only as read-only data and handles pages outside the list", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, total: 1, page: 8, pages: 1 });
    render(<AdminLayout>{await AdminSubscribersPage({ searchParams: Promise.resolve({ page: "8" }) })}</AdminLayout>);
    expect(screen.getByText("На этой странице подписчиков нет.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "На первую" }).getAttribute("href")).toBe("/admin/subscribers?page=1");
    expect(adminFetch).toHaveBeenCalledWith("/subscribers?page=8&page_size=20");
  });

  it("renders page and note statistics using the selected period", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, items: [{ path: "/notes", note_slug: "example", views: 12, uniques: 9 }], total: 1, pages: 1 });
    render(<AdminLayout>{await AdminPagesPage({ searchParams: Promise.resolve({ period: "7d" }) })}</AdminLayout>);
    expect(screen.getByText("Заметка: example")).toBeTruthy();
    expect(adminFetch).toHaveBeenCalledWith("/stats/pages?period=7d&page=1&page_size=20");
  });

  it("shows feedback as plain text with contact details, UTC time and pagination", async () => {
    const message = "First line\n<script>alert('message')</script>";
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, total: 45, page: 2, pages: 3, items: [{
      id: 42, name: "Иван", email: "visitor@example.com", message, created_at: "2026-10-13T12:00:00Z",
    }] });
    const { container } = render(<AdminLayout>{await AdminFeedbackPage({ searchParams: Promise.resolve({ page: "2" }) })}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/feedback?page=2&page_size=20");
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe("Обратная связь");
    expect(screen.getByRole("link", { name: "Обратная связь" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("article", { name: "Сообщение от Иван" }).textContent).toContain(message);
    expect(screen.getByText("visitor@example.com")).toBeTruthy();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("time")?.getAttribute("datetime")).toBe("2026-10-13T12:00:00Z");
    expect(screen.getByRole("link", { name: "Вперёд" }).getAttribute("href")).toBe("/admin/feedback?page=3");
    expect((await axe(container)).violations).toEqual([]);
  });

  it("handles an empty feedback page and preserves the route when returning to the first page", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, total: 1, page: 8, pages: 1 });
    const { container } = render(<AdminLayout>{await AdminFeedbackPage({ searchParams: Promise.resolve({ page: "8" }) })}</AdminLayout>);
    expect(screen.getByText("На этой странице обращений нет.")).toBeTruthy();
    expect(screen.getByRole("link", { name: "На первую" }).getAttribute("href")).toBe("/admin/feedback?page=1");
    expect((await axe(container)).violations).toEqual([]);
  });
});
