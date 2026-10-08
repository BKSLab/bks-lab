import type { Metadata } from "next";
import Link from "next/link";

import { AdminPeriodFilter } from "@/components/admin/AdminFilters";
import { AdminShell } from "@/components/admin/AdminShell";
import { AdminTimeSeries } from "@/components/admin/AdminTimeSeries";
import { adminFetch, requireAdmin } from "@/lib/admin-api";
import { adminMetric, adminNumber, adminPeriod, type AdminSearchParams } from "@/lib/admin-api/params";
import type { AdminOverview, TimeSeriesPoint } from "@/lib/admin-api/types";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Обзор" };

export default async function AdminOverviewPage({ searchParams }: { searchParams: Promise<AdminSearchParams> }) {
  const user = await requireAdmin();
  const params = await searchParams;
  const period = adminPeriod(params.period);
  const metric = adminMetric(params.metric);
  const [overview, points] = await Promise.all([
    adminFetch<AdminOverview>("/overview"),
    adminFetch<TimeSeriesPoint[]>(`/stats/timeseries?period=${period}&metric=${metric}`),
  ]);
  const cards = [
    ["Просмотры сегодня", overview.views_today],
    ["Просмотры за 7 дней", overview.views_7d],
    ["Просмотры за 30 дней", overview.views_30d],
    ["Посетители сегодня", overview.uniques_today],
  ] as const;

  return (
    <AdminShell username={user.username} current="overview">
      <header className="admin-heading"><h1>Обзор сайта</h1><p className="admin-muted">Посещения и интерес к материалам. Все даты и границы дней — UTC.</p></header>
      <dl className="admin-metrics">{cards.map(([label, value]) => <div className="admin-metric" key={label}><dt>{label}</dt><dd>{adminNumber(value)}</dd></div>)}</dl>
      <section className="admin-section" aria-labelledby="admin-dynamics">
        <h2 id="admin-dynamics">Динамика посещений</h2>
        <AdminPeriodFilter action="/admin" period={period} metric={metric} />
        {metric === "uniques" && <p className="admin-muted">Посетители считаются отдельно за каждый день. Один человек в разные дни учитывается повторно.</p>}
        <AdminTimeSeries points={points} label={metric === "views" ? "Просмотры" : "Посетители"} />
      </section>
      <div className="admin-grid-two">
        <section className="admin-section" aria-labelledby="admin-top-pages">
          <h2 id="admin-top-pages">Популярные страницы</h2>
          {overview.top_pages_30d.length ? <table className="admin-table">
            <caption>Просмотры за 30 дней</caption>
            <thead><tr><th scope="col">Страница</th><th scope="col">Просмотры</th></tr></thead>
            <tbody>{overview.top_pages_30d.map((item) => <tr key={item.path}><th scope="row">{item.path}</th><td className="admin-numeric">{adminNumber(item.views)}</td></tr>)}</tbody>
          </table> : <p className="admin-empty">Данных о просмотрах пока нет.</p>}
          <p className="mt-4"><Link className="admin-link" prefetch={false} href="/admin/stats/pages">Все страницы</Link></p>
        </section>
        <section className="admin-section" aria-labelledby="admin-top-referrers">
          <h2 id="admin-top-referrers">Источники переходов</h2>
          {overview.top_referrers_30d.length ? <table className="admin-table">
            <caption>Переходы за 30 дней</caption>
            <thead><tr><th scope="col">Источник</th><th scope="col">Просмотры</th></tr></thead>
            <tbody>{overview.top_referrers_30d.map((item) => <tr key={item.domain}><th scope="row">{item.domain || "Прямой переход"}</th><td className="admin-numeric">{adminNumber(item.views)}</td></tr>)}</tbody>
          </table> : <p className="admin-empty">Источников переходов пока нет.</p>}
          <p className="mt-4"><Link className="admin-link" prefetch={false} href="/admin/stats/referrers">Все источники</Link></p>
        </section>
      </div>
    </AdminShell>
  );
}
