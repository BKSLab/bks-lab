export interface AdminUser {
  username: string;
}

export interface AdminFeedback {
  id: number;
  name: string;
  email: string;
  message: string;
  created_at: string;
}

export interface AdminPaged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export type AdminPeriod = "7d" | "30d" | "90d";
export type AdminMetric = "views" | "uniques";
export type ContentType = "article" | "note" | "project";
export type ContentStatus = "active" | "draft" | "archived";

export interface TimeSeriesPoint {
  date: string;
  value: number;
}

export interface PageStat {
  path: string;
  note_slug: string | null;
  views: number;
  uniques: number;
}

export interface ReferrerStat {
  domain: string;
  views: number;
}

export interface AdminOverview {
  views_today: number;
  views_7d: number;
  views_30d: number;
  uniques_today: number;
  top_pages_30d: { path: string; views: number }[];
  top_referrers_30d: ReferrerStat[];
}

export interface AdminContentItem {
  id: number;
  type: ContentType;
  slug: string;
  title: string;
  category: string | null;
  tags: string[];
  published_at: string | null;
  status: ContentStatus;
  word_count: number;
  views_30d: number;
}

export interface AdminContentDetail extends AdminContentItem {
  excerpt: string | null;
  cover_image: string | null;
  seo_title: string | null;
  seo_description: string | null;
  og_image: string | null;
  related_slug: string | null;
  featured: boolean;
  sort_order: number | null;
  reading_time: number | null;
  content_markdown: string;
  created_at: string;
  updated_at: string;
  views_timeseries_30d: TimeSeriesPoint[];
}

export interface ContentRevisionInfo {
  revision_no: number;
  word_count: number;
  created_at: string;
}

export interface ContentRevisionSnapshot extends ContentRevisionInfo {
  snapshot: AdminContentDetail;
}

export type ContentImageSection = "articles" | "notes" | "projects" | "covers" | "shared";

export interface AdminContentImage {
  id: number;
  path: string;
  original_name: string;
  mime: string;
  size_bytes: number;
  width: number;
  height: number;
  created_at: string;
}

export interface AdminSubscriber {
  email: string;
  subscribed_at: string;
}
