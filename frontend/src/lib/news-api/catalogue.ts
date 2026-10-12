export type SourceCatalogueGroup = "labs" | "engineering" | "business" | "society" | "authors" | "russian" | "tools";
export type SourceCatalogueMode = "rss" | "auto" | "read" | "api";

export interface SourceCatalogueEntry {
  id: string;
  group: SourceCatalogueGroup;
  name: string;
  url: string;
  feedUrl?: string | null;
  extraUrls: string[];
  priority: "A" | "B" | "C" | null;
  connection: string;
  description: string;
  mode: SourceCatalogueMode;
  vendor: boolean;
}

// Suggestions are loaded from /api/admin/news/sources/catalogue.
// These section labels match the bundled research seed.
export const sourceGroups: { id: SourceCatalogueGroup; title: string }[] = [
  {
    "id": "labs",
    "title": "Официальные лаборатории и модели (англ.)"
  },
  {
    "id": "engineering",
    "title": "AI-разработка, код, агенты, RAG и инженерные практики"
  },
  {
    "id": "business",
    "title": "AI в бизнесе, компаниях и B2B"
  },
  {
    "id": "society",
    "title": "Этические, политические, правовые и философские вопросы"
  },
  {
    "id": "authors",
    "title": "Личные сайты и голоса, которые стоит читать напрямую"
  },
  {
    "id": "russian",
    "title": "Русскоязычные источники"
  },
  {
    "id": "tools",
    "title": "Бесплатные API и поисковые ресурсы"
  }
];
