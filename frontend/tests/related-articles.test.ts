import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...await importOriginal<typeof import("@/lib/api")>(),
  getArticles: vi.fn(),
}));

import { getArticles } from "@/lib/api";
import { getRelatedArticles } from "@/lib/api/related-articles";
import type { ArticleSummary, Paged } from "@/lib/api/types";

function article(slug: string, tags: string[], published_at = "2026-10-19"): ArticleSummary {
  return {
    slug, tags, published_at, title: slug, excerpt: "Описание", category: "ai",
    reading_time: 2, cover_image: "/images/articles/1c-async.webp",
  };
}

function paged(items: ArticleSummary[], page: number, pages: number): Paged<ArticleSummary> {
  return { items, page, pages, page_size: 50, total: pages * 50 };
}

beforeEach(() => {
  vi.mocked(getArticles).mockReset();
});

describe("related articles", () => {
  it("scans beyond the first page, matches any tag, deduplicates and preserves date order", async () => {
    const current = article("current", ["FastAPI", "AI"]);
    const newest = article("newest", ["FastAPI", "AI"], "2026-10-18");
    const second = { ...article("second", ["AI"], "2026-10-17"), category: "management" };
    const third = article("third", ["FastAPI"], "2026-10-16");
    vi.mocked(getArticles)
      .mockResolvedValueOnce(paged([
        current,
        ...Array.from({ length: 48 }, (_, index) => article(`unrelated-${index}`, ["other"])),
        newest,
      ], 1, 3))
      .mockResolvedValueOnce(paged([newest, second, third], 2, 3));

    expect(await getRelatedArticles(current)).toEqual([newest, second, third]);
    expect(getArticles).toHaveBeenCalledTimes(2);
    expect(getArticles).toHaveBeenNthCalledWith(1, { page: 1, pageSize: 50 });
    expect(getArticles).toHaveBeenNthCalledWith(2, { page: 2, pageSize: 50 });
  });

  it("does not request articles when the current article has no tags", async () => {
    expect(await getRelatedArticles(article("current", []))).toEqual([]);
    expect(getArticles).not.toHaveBeenCalled();
  });

  it("returns no unrelated fallback when all pages have no shared tags", async () => {
    vi.mocked(getArticles)
      .mockResolvedValueOnce(paged([article("first", ["other"])], 1, 2))
      .mockResolvedValueOnce(paged([article("last", [])], 2, 2));

    expect(await getRelatedArticles(article("current", ["AI"]))).toEqual([]);
    expect(getArticles).toHaveBeenCalledTimes(2);
  });

  it("does not hide unexpected programming errors", async () => {
    const error = new TypeError("Unexpected implementation error");
    vi.mocked(getArticles).mockRejectedValue(error);

    await expect(getRelatedArticles(article("current", ["AI"]))).rejects.toBe(error);
  });
});
