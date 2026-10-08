// Types mirror docs/api_contract.md (public models).

export interface SeoMeta {
  title: string;
  description: string;
  og_image: string;
}

export interface ArticleSummary {
  slug: string;
  title: string;
  excerpt: string;
  category: string;
  published_at: string;
  reading_time: number;
  cover_image: string;
  tags: string[];
}

export interface ArticleDetail extends ArticleSummary {
  content_html: string;
  seo: SeoMeta;
}

export interface NoteRelatedArticle {
  slug: string;
  title: string;
}

export interface Note {
  slug: string;
  title: string;
  excerpt: string;
  published_at: string;
  reading_time: number;
  tags: string[];
  related_article: NoteRelatedArticle | null;
  content_html: string;
}

export type ProjectStatus = "active" | "archived";

export interface ProjectSummary {
  slug: string;
  title: string;
  excerpt: string;
  cover_image: string;
  tags: string[];
  status: ProjectStatus;
  featured: boolean;
  order: number;
}

export interface ProjectDetail extends ProjectSummary {
  content_html: string;
  seo: SeoMeta;
}

export interface Category {
  slug: string;
  title: string;
  articles_count: number;
}

export interface Paged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}
