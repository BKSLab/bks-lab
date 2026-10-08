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

  it("preserves filters in pagination and exposes material details without editing controls", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...paged, items: [item], total: 45, page: 2, pages: 3 });
    const element = await AdminContentPage({ searchParams: Promise.resolve({ type: "article", status: "draft", q: "API", page: "2" }) });
    const { container } = render(<AdminLayout>{element}</AdminLayout>);
    expect(adminFetch).toHaveBeenCalledWith("/content?type=article&status=draft&q=API&page=2&page_size=20");
    expect(screen.getByRole("link", { name: "Архитектура API" }).getAttribute("href")).toBe("/admin/content/1");
    expect(screen.getByRole("link", { name: "Вперёд" }).getAttribute("href")).toContain("status=draft&q=API&page=3");
    expect(screen.queryByRole("button", { name: /Удалить|Редактировать|Создать/ })).toBeNull();
    expect((await axe(container)).violations).toEqual([]);
  });

  it("omits links to unpublished drafts and shows synchronization metadata", async () => {
    vi.mocked(adminFetch).mockResolvedValue({ ...item, synced_at: "2026-10-08T10:00:00Z", content_hash: "abc123", views_timeseries_30d: [] });
    render(<AdminLayout>{await AdminContentDetailPage({ params: Promise.resolve({ id: "1" }) })}</AdminLayout>);
    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(item.title);
    expect(screen.queryByRole("link", { name: "Открыть на сайте" })).toBeNull();
    expect(screen.getByText("abc123")).toBeTruthy();
    expect(screen.getByText("Черновик")).toBeTruthy();
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
});
