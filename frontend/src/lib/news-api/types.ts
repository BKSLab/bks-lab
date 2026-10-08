export type NewsFormat = "longread_candidate" | "short_news_candidate";
export type NewsDecisionValue = "in_work" | "deferred" | "rejected";
export type NewsJobStatus = "queued" | "running" | "completed" | "failed" | "cancelled";
export type NewsScores = Record<"topical_fit" | "significance" | "freshness" | "article_potential", number>;

export interface NewsPaged<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}

export interface NewsTaxonomy {
  id: number;
  name: string;
  description: string;
  active: boolean;
}

export interface NewsSource {
  id: number;
  name: string;
  url: string;
  kind: "rss" | "html";
  config: Record<string, string>;
  active: boolean;
  priority: number;
  trust_score: number;
  vendor_affiliated: boolean;
  interval_hours: number;
  topic_ids: number[];
  category_ids: number[];
  last_success_at: string | null;
  last_error: string | null;
  last_new_count: number;
  health: string;
}

export interface NewsAnalysis {
  id: number;
  is_relevant: boolean;
  category_id: number | null;
  category_name: string | null;
  topics: NewsTaxonomy[];
  suggested_topics: string[];
  scores: NewsScores;
  summary_ru: string;
  editorial_comment_ru: string;
  recommended_formats: NewsFormat[];
  confidence: number;
  needs_verification: boolean;
  news_score: number;
  article_score: number;
  model: string;
  prompt_version: string;
  created_at: string;
}

export interface NewsDecision {
  id: number;
  decision: NewsDecisionValue;
  format: NewsFormat;
  comment: string;
  editor: string;
  created_at: string;
}

export interface NewsItem {
  id: number;
  source_id: number;
  source_name: string;
  url: string;
  canonical_url: string | null;
  title: string;
  excerpt: string;
  published_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  updated_at: string | null;
  status: "pending_analysis" | "analyzed";
  duplicate_of_id: number | null;
  analysis: NewsAnalysis | null;
  decision: NewsDecision | null;
}

export interface NewsItemDetail extends NewsItem {
  content: string | null;
  analysis_history: NewsAnalysis[];
  decision_history: NewsDecision[];
}

export interface NewsJobAccepted { job_id: number; status: NewsJobStatus }

export interface NewsPreviewItem { title: string; url: string; published_at: string | null; excerpt?: string }
export interface NewsDiscovery { kind: "rss" | "html"; url: string; items: NewsPreviewItem[]; warnings: string[] }

export interface NewsJob {
  id: number;
  kind: "collect" | "discover" | "analyze";
  status: NewsJobStatus;
  source_id: number | null;
  item_id: number | null;
  attempts: number;
  progress: Record<string, unknown>;
  error: string | null;
  result: Record<string, unknown> | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  heartbeat_at: string | null;
}

export interface NewsRun {
  id: number;
  source_id: number;
  source_name: string;
  job_id: number | null;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at: string | null;
  new_count: number;
  updated_count: number;
  unchanged_count: number;
  error: string | null;
}

export interface NewsSettings {
  enabled: boolean;
  timezone: string;
  schedule: string[];
  editorial_policy: string;
  exclusions: string;
  news_weights: NewsScores;
  article_weights: NewsScores;
  initial_lookback_days: number;
  max_items_per_source: number;
  max_excerpt_chars: number;
  analysis_batch_size: number;
  text_retention_days: number;
  history_retention_days: number;
  llm_configured: boolean;
  llm_provider: string;
  llm_model: string;
}
