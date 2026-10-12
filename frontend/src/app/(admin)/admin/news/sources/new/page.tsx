import type { Metadata } from "next";
import Link from "next/link";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsSourceForm } from "@/components/admin/news/NewsSourceForm";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { firstParam, type AdminSearchParams } from "@/lib/admin-api/params";
import type { SourceCatalogueEntry } from "@/lib/news-api/catalogue";
import type { NewsTaxonomy } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Добавить источник" };

export default async function NewsNewSourcePage({ searchParams }: { searchParams?: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const catalogueId = firstParam((await searchParams ?? {}).catalogue);
  const [topics, categories, sourceCatalogue] = await Promise.all([
    adminFetch<NewsTaxonomy[]>("/news/topics"),
    adminFetch<NewsTaxonomy[]>("/news/categories"),
    adminFetch<SourceCatalogueEntry[]>("/news/sources/catalogue"),
  ]);
  const selected = sourceCatalogue.find(entry => entry.id === catalogueId);
  const catalogueEntry = selected && (selected.mode === "rss" || selected.mode === "auto") ? selected : undefined;
  return <NewsShell username={user.username} current="sources" title="Новый источник" description="Укажите адрес, проверьте найденные публикации и сохраните настройки сбора.">
    <div className="news-actions"><Link className="admin-link" prefetch={false} href="/admin/news/sources">К источникам</Link><Link className="admin-link" prefetch={false} href="/admin/news/sources/catalogue">Весь каталог ({sourceCatalogue.length})</Link></div>
    {catalogueId && !catalogueEntry && <p role="status" className="admin-muted">Этот пункт каталога недоступен для подключения через RSS или HTML. Выберите источник в каталоге или укажите свой адрес.</p>}
    <NewsSourceForm key={catalogueEntry?.id ?? "custom"} topics={topics} categories={categories} catalogueEntry={catalogueEntry} catalogue={sourceCatalogue} />
  </NewsShell>;
}
