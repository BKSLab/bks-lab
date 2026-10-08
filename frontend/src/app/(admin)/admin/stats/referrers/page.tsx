import type { Metadata } from "next";

import { AdminPeriodFilter } from "@/components/admin/AdminFilters";
import { AdminShell } from "@/components/admin/AdminShell";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminNumber, adminPeriod, type AdminSearchParams } from "@/lib/admin-api/params";
import type { ReferrerStat } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Источники переходов" };

export default async function AdminReferrersPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const period = adminPeriod(params.period);
  const items = await adminFetch<ReferrerStat[]>(`/stats/referrers?period=${period}`);

  return <AdminShell username={user.username} current="referrers">
    <header className="admin-heading"><h1>Источники переходов</h1><p className="admin-muted">До 50 источников по количеству просмотров. Даты — UTC.</p></header>
    <section className="admin-section" aria-label="Данные по источникам">
      <AdminPeriodFilter action="/admin/stats/referrers" period={period} />
      {items.length ? <table className="admin-table">
        <caption>Источники за {period.slice(0, -1)} дней</caption>
        <thead><tr><th scope="col">Источник</th><th scope="col">Просмотры</th></tr></thead>
        <tbody>{items.map((item) => <tr key={item.domain}><th scope="row">{item.domain || "Прямой переход"}</th><td className="admin-numeric">{adminNumber(item.views)}</td></tr>)}</tbody>
      </table> : <p className="admin-empty">За этот период переходов пока нет.</p>}
    </section>
  </AdminShell>;
}
