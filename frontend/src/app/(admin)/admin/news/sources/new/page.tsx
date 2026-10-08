import type { Metadata } from "next";
import Link from "next/link";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsSourceForm } from "@/components/admin/news/NewsSourceForm";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import type { NewsTaxonomy } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Добавить источник" };

export default async function NewsNewSourcePage() {
  const user = await requireAdmin();
  const [topics, categories] = await Promise.all([adminFetch<NewsTaxonomy[]>("/news/topics"), adminFetch<NewsTaxonomy[]>("/news/categories")]);
  return <NewsShell username={user.username} current="sources" title="Новый источник" description="Укажите адрес, проверьте найденные публикации и сохраните настройки сбора.">
    <div><Link className="admin-link" prefetch={false} href="/admin/news/sources">К источникам</Link></div><NewsSourceForm topics={topics} categories={categories} />
  </NewsShell>;
}
