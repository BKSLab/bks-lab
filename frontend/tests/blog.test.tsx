import { render, screen, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { axe } from "vitest-axe";

vi.mock("next/navigation", () => ({
  notFound: vi.fn(() => { throw new Error("NEXT_NOT_FOUND"); }),
}));
vi.mock("@/lib/api", () => ({ getArticle: vi.fn(), getArticles: vi.fn() }));

import ArticlePage from "@/app/(public)/blog/post/[slug]/page";
import { BlogPageContent } from "@/components/blog/BlogPageContent";
import { getArticle, getArticles } from "@/lib/api";
import type { ArticleDetail, ArticleSummary } from "@/lib/api/types";

const article: ArticleDetail = {
  slug: "current", title: "Текущая статья", excerpt: "Описание", category: "ai",
  published_at: "2026-10-19", reading_time: 2, cover_image: "/images/articles/1c-async.webp",
  tags: ["AI"], content_html: "<p>Текст открытой статьи.</p>",
  seo: { title: "Текущая статья", description: "Описание", og_image: "/og/blog.jpg" },
};
const related: ArticleSummary = { ...article, slug: "related", title: "Ещё об AI", published_at: "2026-10-18" };

beforeEach(() => {
  vi.mocked(getArticle).mockReset().mockResolvedValue(article);
  vi.mocked(getArticles).mockReset().mockImplementation(async ({ page = 1, pageSize = 3 } = {}) => ({
    items: [article, related], total: 9, page, page_size: pageSize, pages: 3,
  }));
});

describe("blog views", () => {
  it.each([{}, { page: 2 }, { category: "ai" }, { category: "ai", page: 2 }])(
    "keeps server-rendered categories, articles and pagination without the removed blocks: %j",
    async (params) => {
      const html = renderToStaticMarkup(await BlogPageContent(params));
      const doc = new DOMParser().parseFromString(html, "text/html");
      expect(doc.querySelectorAll("h1")).toHaveLength(1);
      expect(doc.querySelector('nav[aria-label="Категории статей"]')).not.toBeNull();
      expect(doc.querySelector('a[href="/blog/post/current"]')).not.toBeNull();
      expect(doc.querySelector('nav[aria-label="Страницы публикаций"]')).not.toBeNull();
      expect(doc.querySelector('[role="search"], input[type="search"], input[type="email"]')).toBeNull();
      expect(doc.body.textContent).not.toMatch(/Подписка|Популярные темы|Заметки на полях|Поиск по статьям/);
      expect(getArticles).toHaveBeenCalledExactlyOnceWith({ page: params.page ?? 1, pageSize: 3, category: params.category });
    },
  );

  it("renders related headlines and thumbnails after the open article with accessible structure", async () => {
    vi.mocked(getArticles).mockResolvedValue({ items: [article, related], total: 2, page: 1, page_size: 50, pages: 1 });
    const { container } = render(<main>{await ArticlePage({ params: Promise.resolve({ slug: article.slug }) })}</main>);
    const section = screen.getByRole("region", { name: "Похожие статьи" });
    const link = within(section).getByRole("link", { name: /Ещё об AI/ });
    expect(link.getAttribute("href")).toBe("/blog/post/related");
    expect(link.querySelector("img")?.getAttribute("alt")).toBe("");
    expect(within(section).getAllByRole("listitem")).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByText("Текст открытой статьи.")).toBeTruthy();
    expect(await axe(container)).toHaveNoViolations();
  });

  it("hides the related section when there are no matching articles", async () => {
    vi.mocked(getArticles).mockResolvedValue({ items: [article], total: 1, page: 1, page_size: 50, pages: 1 });
    render(await ArticlePage({ params: Promise.resolve({ slug: article.slug }) }));
    expect(screen.queryByRole("region", { name: "Похожие статьи" })).toBeNull();
  });
});
