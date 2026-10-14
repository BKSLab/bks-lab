import type { Metadata } from "next";
import Link from "next/link";
import { AdminPagination } from "@/components/admin/AdminPagination";
import { NewsItemRow } from "@/components/admin/news/NewsItemRow";
import { NewsShell } from "@/components/admin/news/NewsShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminHref, adminPage, type AdminSearchParams } from "@/lib/admin-api/params";
import type { NewsItem, NewsPaged } from "@/lib/news-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "План публикаций" };

export default async function NewsPlanPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const data = await adminFetch<NewsPaged<NewsItem>>(adminHref("/news/items", {
    decision: "in_work", page: adminPage(params.page), page_size: 20,
  }));

  return <NewsShell username={user.username} current="plan" title="План публикаций" description="Материалы, которые вы выбрали для подготовки публикаций. Выжимка, первоисточник и редакторские заметки — в одном месте.">
    <section className="admin-section" aria-label="Материалы в плане">
      <div className="news-actions"><Link className="admin-button" prefetch={false} href="/admin/news/items">Выбрать материалы из подборок</Link></div>
      <p className="admin-muted">В плане: {data.total}.</p>
      {data.items.length ? <ul className="news-items" aria-label="План публикаций">{data.items.map(item => <li key={item.id}><NewsItemRow item={item} planned /></li>)}</ul>
        : <div className="admin-empty"><p>{data.total ? "На этой странице нет материалов. Вернитесь на первую страницу плана." : "План пока пуст. Откройте подборки и нажмите «Добавить в план» под понравившейся выжимкой."}</p></div>}
      <AdminPagination path="/admin/news/plan" page={data.page} total={data.total} pages={data.pages ?? Math.ceil(data.total / data.page_size)} />
    </section>
  </NewsShell>;
}
