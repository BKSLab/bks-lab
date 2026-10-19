import { ApiError, getArticles } from "@/lib/api";
import type { ArticleSummary, Paged } from "./types";

const RELATED_ARTICLE_LIMIT = 3;
const ARTICLE_SCAN_PAGE_SIZE = 50;

export async function getRelatedArticles(
  article: Pick<ArticleSummary, "slug" | "tags">,
): Promise<ArticleSummary[]> {
  const tags = new Set(article.tags);
  if (!tags.size) return [];

  const related: ArticleSummary[] = [];
  const seen = new Set([article.slug]);
  let page = 1;

  // The API has no tag filter. Scan its date-ordered pages until enough match.
  while (true) {
    let data: Paged<ArticleSummary>;
    try {
      data = await getArticles({ page, pageSize: ARTICLE_SCAN_PAGE_SIZE });
    } catch (error) {
      if (error instanceof ApiError) return related;
      throw error;
    }
    for (const candidate of data.items) {
      if (seen.has(candidate.slug) || !candidate.tags.some((tag) => tags.has(tag))) {
        continue;
      }
      seen.add(candidate.slug);
      related.push(candidate);
      if (related.length === RELATED_ARTICLE_LIMIT) return related;
    }
    if (page >= data.pages || !data.items.length) return related;
    page += 1;
  }
}
