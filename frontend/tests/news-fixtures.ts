import type { NewsAnalysis, NewsItemDetail, NewsJob, NewsSettings, NewsSource, NewsTaxonomy } from "@/lib/news-api/types";

export const newsTopic: NewsTaxonomy = { id: 1, name: "AI Engineering", description: "Практическая разработка", active: true };
export const newsCategory: NewsTaxonomy = { id: 2, name: "Исследования", description: "Новые результаты", active: true };
export const newsSource: NewsSource = {
  id: 7, name: "Технический блог", url: "https://example.org/feed.xml", kind: "rss", config: {}, active: false,
  priority: 50, trust_score: 70, vendor_affiliated: false, interval_hours: 8, topic_ids: [1], category_ids: [2],
  last_success_at: null, last_error: null, last_new_count: 0, health: "unknown",
};
export const newsAnalysis: NewsAnalysis = {
  id: 3, is_relevant: true, category_id: 2, category_name: "Исследования", topics: [newsTopic], suggested_topics: [],
  scores: { topical_fit: 90, significance: 80, freshness: 70, article_potential: 90 }, summary_ru: "Исследование качества агентов.",
  editorial_comment_ru: "Подходит для разбора инженерных ограничений.", recommended_formats: ["longread_candidate", "short_news_candidate"],
  confidence: 0.86, needs_verification: true, news_score: 82, article_score: 86, model: "example/model", prompt_version: "v1", created_at: "2026-10-08T08:30:00Z",
};
export const newsItem: NewsItemDetail = {
  id: 4, source_id: 7, source_name: "Технический блог", url: "https://example.org/article", canonical_url: null,
  title: "Проверка качества AI-агентов", excerpt: "Краткое описание", published_at: "2026-10-08T08:00:00Z", first_seen_at: "2026-10-08T08:10:00Z",
  last_seen_at: "2026-10-08T08:10:00Z", updated_at: null, status: "analyzed", duplicate_of_id: null, analysis: newsAnalysis, decision: null,
  content: "Текст первоисточника", analysis_history: [newsAnalysis], decision_history: [],
};
export const newsJob: NewsJob = {
  id: 9, kind: "discover", status: "completed", source_id: null, item_id: null, attempts: 1,
  progress: {}, error: null, result: { kind: "rss", url: "https://example.org/feed.xml", items: [{ title: "Новая публикация", url: "https://example.org/article", published_at: "2026-10-08T08:00:00Z" }], warnings: [] },
  created_at: "2026-10-08T08:00:00Z", started_at: "2026-10-08T08:00:01Z", completed_at: "2026-10-08T08:00:02Z", heartbeat_at: "2026-10-08T08:00:01Z",
};
export const newsSettings: NewsSettings = {
  enabled: true, timezone: "Europe/Samara", schedule: ["08:00", "14:00", "20:00"], editorial_policy: "AI и современная разработка", exclusions: "Рекламные обещания",
  news_weights: { topical_fit: 40, significance: 25, freshness: 25, article_potential: 10 },
  article_weights: { topical_fit: 35, significance: 25, freshness: 10, article_potential: 30 },
  initial_lookback_days: 30, max_items_per_source: 50, max_excerpt_chars: 3000, analysis_batch_size: 20, text_retention_days: 90, history_retention_days: 180,
  llm_configured: true, llm_provider: "provider", llm_model: "example/model",
};
