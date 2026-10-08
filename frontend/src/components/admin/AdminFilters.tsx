import type { AdminMetric, AdminPeriod } from "@/lib/admin-api/types";

export function AdminPeriodFilter({ action, period, metric }: {
  action: string;
  period: AdminPeriod;
  metric?: AdminMetric;
}) {
  return (
    <form action={action} method="get" className="admin-filters">
      <div className="admin-field">
        <label htmlFor="admin-period">Период</label>
        <select id="admin-period" name="period" defaultValue={period}>
          <option value="7d">7 дней</option>
          <option value="30d">30 дней</option>
          <option value="90d">90 дней</option>
        </select>
      </div>
      {metric && <div className="admin-field">
        <label htmlFor="admin-metric">Показатель</label>
        <select id="admin-metric" name="metric" defaultValue={metric}>
          <option value="views">Просмотры</option>
          <option value="uniques">Посетители за день</option>
        </select>
      </div>}
      <button type="submit" className="admin-button">Показать</button>
    </form>
  );
}
