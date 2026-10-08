import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const nav = vi.hoisted(() => ({ query: "", push: vi.fn() }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(nav.query),
  useRouter: () => ({ push: nav.push }),
}));
vi.mock("@/lib/api", () => ({ apiFetch: vi.fn() }));

import { BlogSearch } from "@/components/blog/BlogSearch";
import { apiFetch } from "@/lib/api";
import type { ArticleSummary, Paged } from "@/lib/api/types";

const empty: Paged<ArticleSummary> = { items: [], total: 0, pages: 0, page: 1, page_size: 3 };
const article: ArticleSummary = { slug: "found", title: "Найденная статья", excerpt: "Описание", category: "development", published_at: "2026-10-07", reading_time: 2, cover_image: "/images/articles/1c-async.webp", tags: [] };

beforeEach(() => { nav.query = ""; nav.push.mockReset(); vi.mocked(apiFetch).mockReset(); });

describe("blog search", () => {
  it("validates input and navigates to page one of the current category", () => {
    render(<BlogSearch initial={empty} base="/blog/development" category="development" />);
    const input = screen.getByRole("searchbox");
    fireEvent.change(input, { target: { value: "a" } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(screen.getByRole("alert").textContent).toContain("от 2 до 100");
    expect(document.activeElement).toBe(input);
    expect(nav.push).not.toHaveBeenCalled();
    fireEvent.change(input, { target: { value: " FastAPI " } });
    fireEvent.click(screen.getByRole("button", { name: "Найти" }));
    expect(nav.push).toHaveBeenCalledWith("/blog/development?q=FastAPI", { scroll: false });
  });
  it("loads deep-link search and preserves query pagination", async () => {
    nav.query = "q=FastAPI&page=2";
    vi.mocked(apiFetch).mockResolvedValue({ ...empty, items: [article], page: 2, pages: 3, total: 7 });
    render(<BlogSearch initial={empty} base="/blog" />);
    expect(screen.getByRole("status").textContent).toBe("Ищем статьи…");
    await screen.findByRole("heading", { name: article.title });
    expect(apiFetch).toHaveBeenCalledWith("/articles?q=FastAPI&page=2&page_size=3", { tags: ["articles"] });
    expect(screen.getByRole("status").textContent).toBe("Найдено статей: 7");
    expect(screen.getByRole("link", { name: "Далее" }).getAttribute("href")).toBe("/blog?q=FastAPI&page=3");
  });
  it("ignores stale responses after back/forward changes the query", async () => {
    let resolveOld!: (value: Paged<ArticleSummary>) => void;
    nav.query = "q=old";
    vi.mocked(apiFetch).mockImplementationOnce(() => new Promise(resolve => { resolveOld = resolve; }));
    const { rerender } = render(<BlogSearch initial={empty} base="/blog" />);
    nav.query = "q=new";
    vi.mocked(apiFetch).mockResolvedValue({ ...empty, items: [article], total: 1, pages: 1 });
    rerender(<BlogSearch initial={empty} base="/blog" />);
    await screen.findByRole("heading", { name: article.title });
    await act(async () => { resolveOld(empty); });
    expect(screen.getByRole("heading", { name: article.title })).toBeTruthy();
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("new");
    nav.query = "";
    rerender(<BlogSearch initial={empty} base="/blog" />);
    expect(screen.getByRole("status").textContent).toBe("Статей в разделе: 0");
  });
  it("distinguishes an API failure from an empty result and retries", async () => {
    nav.query = "q=API";
    vi.mocked(apiFetch).mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(empty);
    render(<BlogSearch initial={empty} base="/blog" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Не удалось");
    fireEvent.click(screen.getByRole("button", { name: "Повторить поиск" }));
    await waitFor(() => expect(screen.getByRole("status").textContent).toBe("Найдено статей: 0"));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
