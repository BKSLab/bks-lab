import type { NewsAnalysis, NewsDecision, NewsItemDetail, NewsJob, NewsRun, NewsRunItem, NewsSettings, NewsSource, NewsTaxonomy } from "@/lib/news-api/types";

export const newsDecision: NewsDecision = {
  id: 1, decision: "in_work", format: "short_news_candidate", comment: "Проверить цифры", editor: "owner", created_at: "2026-10-14T08:00:00Z",
};

export const newsTopic: NewsTaxonomy = { id: 1, name: "AI Engineering", description: "Практическая разработка", active: true };
export const newsCategory: NewsTaxonomy = { id: 2, name: "Исследования", description: "Новые результаты", active: true };
export const newsSource: NewsSource = {
  id: 7, slug: "tehnicheskiy-blog", name: "Технический блог", description: "Практика современной разработки и исследования AI.", url: "https://example.org/feed.xml", active: false,
  schedule: { mode: "daily", times: ["08:00", "20:00"] }, next_check_at: null,
  last_success_at: null, last_error: null, last_new_count: 0, health: "unknown",
};
export const newsAnalysis: NewsAnalysis = {
  id: 3, is_relevant: true, category_id: 2, category_name: "Исследования", topics: [newsTopic], suggested_topics: [],
  scores: { topical_fit: 90, significance: 80, freshness: 70, article_potential: 90 }, summary_ru: "Исследование качества агентов.",
  editorial_comment_ru: "Подходит для разбора инженерных ограничений.", recommended_formats: ["longread_candidate", "short_news_candidate"],
  confidence: 0.86, needs_verification: true, news_score: 82, article_score: 86, model: "example/model", prompt_version: "v1", created_at: "2026-10-08T08:30:00Z",
};
export const newsItem: NewsItemDetail = {
  id: 4, source_id: 7, source_slug: newsSource.slug, source_name: "Технический блог", url: "https://example.org/article", canonical_url: null,
  title: "Проверка качества AI-агентов", excerpt: "Краткое описание", published_at: "2026-10-08T08:00:00Z", first_seen_at: "2026-10-08T08:10:00Z",
  last_seen_at: "2026-10-08T08:10:00Z", updated_at: null, status: "analyzed", duplicate_of_id: null, analysis: newsAnalysis, decision: null,
  analysis_state: "analyzed", analysis_error: null, collection_warning: null,
  content: "Текст первоисточника", analysis_history: [newsAnalysis], decision_history: [],
};
export const newsJob: NewsJob = {
  id: 9, slug: "proverka-istochnika-20261008-080000", kind: "discover", status: "completed", source_id: null, source_slug: null, source_name: null, item_id: null, attempts: 1,
  progress: {}, error: null, result: { kind: "rss", url: "https://example.org/feed.xml", items: [{ title: "Новая публикация", url: "https://example.org/article", published_at: "2026-10-08T08:00:00Z" }], warnings: [] },
  created_at: "2026-10-08T08:00:00Z", started_at: "2026-10-08T08:00:01Z", completed_at: "2026-10-08T08:00:02Z", heartbeat_at: "2026-10-08T08:00:01Z",
};
export const newsCollectJob: NewsJob = {
  ...newsJob, slug: "sbor-vseh-istochnikov-20261008-080000", kind: "collect", result: null,
  progress: { sources_total: 1, sources_done: 1, new_count: 1, unchanged_count: 2, skipped_count: 1, warnings: 1 },
  completed_at: "2026-10-08T08:02:30Z",
};
export const newsRun: NewsRun = {
  id: 11, source_id: newsSource.id, source_slug: newsSource.slug, source_name: newsSource.name,
  source_url: newsSource.url, source_kind: "rss", job_id: newsCollectJob.id, job_slug: newsCollectJob.slug,
  status: "completed", started_at: newsCollectJob.started_at!, completed_at: newsCollectJob.completed_at,
  new_count: 1, updated_count: 0, unchanged_count: 2, skipped_count: 1, warning_count: 1,
  error: null, http_status: 200, not_modified: false, limit_reached: false, diagnostics_truncated: false,
  parameters: { cutoff: "2026-09-08T08:00:00Z", initial_lookback_days: 30, max_items_per_source: 50, max_excerpt_chars: 3000, first_run: true, conditional_request: false, mode: "collect", trigger: "manual" },
};
export const newsRunItem: NewsRunItem = {
  id: 21, run_id: newsRun.id, source_slug: newsSource.slug, source_name: newsSource.name, item_id: newsItem.id,
  title: newsItem.title, url: newsItem.url, outcome: "new", reason: "Новая публикация сохранена.", warning: null,
  stage: "storage", preserved_previous: false, analysis_status: "completed", analysis_reason: null, analysis_job_slug: "analiz-materiala-20261008-080005",
};
export const newsSettings: NewsSettings = {
  enabled: true, editorial_policy: "AI и современная разработка", exclusions: "Рекламные обещания",
  news_weights: { topical_fit: 40, significance: 25, freshness: 25, article_potential: 10 },
  article_weights: { topical_fit: 35, significance: 25, freshness: 10, article_potential: 30 },
  initial_lookback_days: 30, max_items_per_source: 50, max_excerpt_chars: 3000, analysis_batch_size: 20, text_retention_days: 90, history_retention_days: 180,
  llm_configured: true, llm_provider: "provider", llm_model: "example/model",
};
