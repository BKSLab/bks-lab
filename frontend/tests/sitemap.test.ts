// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import sitemap, { revalidate } from "@/app/sitemap";
import robots from "@/app/robots";
import { ApiError } from "@/lib/api";
import type { ArticleSummary, Note } from "@/lib/api/types";

const fetchMock = vi.fn<typeof fetch>();
const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const articles: ArticleSummary[] = Array.from({ length: 56 }, (_, index) => ({
  slug: `article-${index + 1}`, title: `Article ${index + 1}`, excerpt: "Summary",
  category: "development", published_at: new Date(Date.UTC(2026, 9, 8 - index)).toISOString(),
  reading_time: 3, cover_image: "/images/articles/accessibility.webp", tags: [],
}));
const notes: Note[] = Array.from({ length: 7 }, (_, index) => ({
  slug: `note-${index + 1}`, title: `Note ${index + 1}`, excerpt: "Summary",
  published_at: new Date(Date.UTC(2026, 9, 8 - index)).toISOString(),
  reading_time: 1, tags: [], related_article: null, content_html: "<p>Note</p>",
}));

beforeEach(() => {
  vi.stubGlobal("fetch", fetchMock);
  vi.stubEnv("SITE_URL", "https://bks-lab.example");
  vi.stubEnv("API_INTERNAL_URL", "http://backend:8000");
  vi.stubEnv("NEXT_PHASE", "phase-production-server");
  fetchMock.mockReset();
});
afterEach(() => { vi.unstubAllGlobals(); vi.unstubAllEnvs(); vi.restoreAllMocks(); });

describe("public sitemap", () => {
  it("walks every API page and includes public index pages, categories and dated content", async () => {
    fetchMock.mockImplementation(async (input) => {
      const url = new URL(String(input));
      if (url.pathname === "/api/v1/projects") return json([{ slug: "demo" }]);
      if (url.pathname === "/api/v1/categories") return json([
        { slug: "development", title: "Разработка", articles_count: 56 },
        { slug: "ai", title: "AI", articles_count: 0 },
      ]);
      const items = url.pathname === "/api/v1/articles" ? articles : notes;
      const page = Number(url.searchParams.get("page"));
      const size = Number(url.searchParams.get("page_size"));
      return json({ items: items.slice((page - 1) * size, page * size), total: items.length, page, page_size: size, pages: Math.ceil(items.length / size) });
    });
    const result = await sitemap();
    const urls = result.map((entry) => entry.url);
    for (const path of ["/", "/about", "/contacts", "/privacy", "/projects", "/projects/demo", "/blog", "/blog/page/19", "/blog/development/page/19", "/blog/ai", "/blog/post/article-56", "/notes", "/notes/page/3"]) {
      expect(urls).toContain(`https://bks-lab.example${path}`);
    }
    expect(urls.some((url) => /#|\?|\/admin|\/api/.test(url))).toBe(false);
    expect(new Set(urls).size).toBe(urls.length);
    expect(result.find((entry) => entry.url.endsWith("/blog/post/article-56"))?.lastModified).toBe(articles[55].published_at);
    expect(result.find((entry) => entry.url.endsWith("/notes/page/3"))?.lastModified).toBe(notes[6].published_at);
    expect(result.find((entry) => entry.url.endsWith("/projects/demo"))).not.toHaveProperty("lastModified");
    expect(result.find((entry) => entry.url.endsWith("/privacy"))).not.toHaveProperty("lastModified");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/articles?page=2&page_size=50"))).toBe(true);
    expect(revalidate).toBe(300);
  });

  it("allows an offline build with a visible warning and a later ISR retry", async () => {
    vi.stubEnv("NEXT_PHASE", "phase-production-build");
    fetchMock.mockRejectedValue(new TypeError("offline"));
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const result = await sitemap();
    expect(result).toHaveLength(7);
    expect(warn).toHaveBeenCalledWith(expect.stringContaining("ISR will retry"));
    expect(revalidate).toBeGreaterThan(0);
  });

  it("throws on an outage during regeneration to preserve the last successful sitemap", async () => {
    fetchMock.mockRejectedValue(new TypeError("offline"));
    await expect(sitemap()).rejects.toBeInstanceOf(ApiError);
  });

  it("does not turn backend application errors into a valid but incomplete sitemap", async () => {
    vi.stubEnv("NEXT_PHASE", "phase-production-build");
    fetchMock.mockResolvedValue(json({ detail: "content sync failed" }, 500));
    await expect(sitemap()).rejects.toMatchObject({ status: 500 });
  });

  it("links the sitemap from robots and excludes the private route prefixes", () => {
    expect(robots()).toEqual({
      rules: { userAgent: "*", allow: "/", disallow: ["/admin", "/api"] },
      sitemap: "https://bks-lab.example/sitemap.xml",
    });
  });
});
