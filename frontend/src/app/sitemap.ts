import type { MetadataRoute } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";
import { apiFetch, isApiUnavailable } from "@/lib/api";
import type { ArticleSummary, Category, Note, Paged, ProjectSummary } from "@/lib/api/types";
import { absoluteUrl, ARTICLE_PAGE_SIZE, NOTE_PAGE_SIZE, pageHref } from "@/lib/content";

export const revalidate = 300;

const staticPaths = ["/", "/about", "/contacts", "/privacy", "/projects", "/blog", "/notes"];

async function allPages<T>(path: string, tag: string): Promise<T[]> {
  const request = (page: number) => apiFetch<Paged<T>>(`${path}?page=${page}&page_size=50`, { tags: [tag] });
  const first = await request(1);
  const items = [...first.items];
  // Bound concurrent work even after the content library has grown.
  for (let page = 2; page <= first.pages; page += 5) {
    const batch = await Promise.all(Array.from(
      { length: Math.min(5, first.pages - page + 1) },
      (_, offset) => request(page + offset),
    ));
    items.push(...batch.flatMap((result) => result.items));
  }
  return items;
}

function latestDate(items: { published_at: string }[]): string | undefined {
  return items.reduce<string | undefined>((latest, item) => (
    !latest || Date.parse(item.published_at) > Date.parse(latest) ? item.published_at : latest
  ), undefined);
}

function indexPages(base: string, items: { published_at: string }[], pageSize: number): MetadataRoute.Sitemap {
  return Array.from({ length: Math.max(1, Math.ceil(items.length / pageSize)) }, (_, index) => {
    const lastModified = latestDate(items.slice(index * pageSize, (index + 1) * pageSize));
    return {
      url: absoluteUrl(pageHref(base, index + 1)),
      ...(lastModified ? { lastModified } : {}),
    };
  });
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  let articles: ArticleSummary[];
  let notes: Note[];
  let projects: ProjectSummary[];
  let categories: Category[];
  try {
    [articles, notes, projects, categories] = await Promise.all([
      allPages<ArticleSummary>("/articles", "articles"),
      allPages<Note>("/notes", "notes"),
      apiFetch<ProjectSummary[]>("/projects", { tags: ["projects"] }),
      apiFetch<Category[]>("/categories", { tags: ["articles"] }),
    ]);
  } catch (error) {
    if (process.env.NEXT_PHASE === PHASE_PRODUCTION_BUILD && isApiUnavailable(error)) {
      console.warn("Sitemap: backend unavailable during build; static routes only. ISR will retry after deployment.");
      return staticPaths.map((path) => ({ url: absoluteUrl(path) }));
    }
    // Throw during regeneration so Next preserves the last successful sitemap.
    throw error;
  }
  return [
    ...staticPaths.filter((path) => path !== "/blog" && path !== "/notes").map((path) => ({ url: absoluteUrl(path) })),
    ...indexPages("/blog", articles, ARTICLE_PAGE_SIZE),
    ...categories.flatMap((category) => indexPages(
      `/blog/${category.slug}`,
      articles.filter((article) => article.category === category.slug),
      ARTICLE_PAGE_SIZE,
    )),
    ...articles.map((article) => ({ url: absoluteUrl(`/blog/post/${article.slug}`), lastModified: article.published_at })),
    ...projects.map((project) => ({ url: absoluteUrl(`/projects/${project.slug}`) })),
    ...indexPages("/notes", notes, NOTE_PAGE_SIZE),
  ];
}
