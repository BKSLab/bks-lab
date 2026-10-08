import type { Metadata } from "next";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsTaxonomyManager } from "@/components/admin/news/NewsTaxonomyManager";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import type { NewsTaxonomy } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Темы и рубрики" };

export default async function NewsTopicsPage() {
  const user = await requireAdmin();
  const [topics, categories] = await Promise.all([adminFetch<NewsTaxonomy[]>("/news/topics"), adminFetch<NewsTaxonomy[]>("/news/categories")]);
  return <NewsShell username={user.username} current="topics" title="Темы и рубрики" description="Модель выбирает рубрики и темы из активных записей. Описание помогает точнее отбирать материалы.">
    <NewsTaxonomyManager topics={topics} categories={categories} />
  </NewsShell>;
}
