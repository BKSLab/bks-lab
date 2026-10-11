import type { Metadata } from "next";
import Link from "next/link";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { NewsSourceCatalogue } from "@/components/admin/news/NewsSourceCatalogue";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { sourceCatalogue, sourceGroups } from "@/lib/news-api/catalogue";
import type { NewsSource } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Каталог источников" };

export default async function NewsCataloguePage() {
  const user = await requireAdmin();
  const sources = await adminFetch<NewsSource[]>("/news/sources");
  return <NewsShell username={user.username} current="catalogue" title="Каталог источников" description={`Все ${sourceCatalogue.length} позиций из исследовательского списка в ${sourceGroups.length} разделах: публикации, авторские сайты, ресурсы для чтения и API.`}>
    <div className="news-actions"><Link className="admin-link" prefetch={false} href="/admin/news/sources">Подключённые источники</Link><Link className="admin-button" prefetch={false} href="/admin/news/sources/new">Добавить свой источник</Link></div>
    <NewsSourceCatalogue sources={sources} />
  </NewsShell>;
}
