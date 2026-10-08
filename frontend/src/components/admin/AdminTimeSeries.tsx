import { adminDate, adminNumber } from "@/lib/admin-api/params";
import type { TimeSeriesPoint } from "@/lib/admin-api/types";

import { AdminChart } from "./AdminChart";

export function AdminTimeSeries({ points, label }: { points: TimeSeriesPoint[]; label: string }) {
  if (!points.length) return <p className="admin-empty">За этот период данных пока нет.</p>;
  return (
    <>
      <AdminChart points={points} />
      {points.every((point) => point.value === 0) && <p className="admin-muted">За этот период посещений пока нет.</p>}
      <details className="admin-chart-data">
        <summary>Данные графика в таблице</summary>
        <table className="admin-table">
          <caption>{label} по дням, UTC</caption>
          <thead><tr><th scope="col">Дата</th><th scope="col">{label}</th></tr></thead>
          <tbody>{points.map((point) => <tr key={point.date}>
            <th scope="row"><time dateTime={point.date}>{adminDate(point.date)}</time></th>
            <td className="admin-numeric">{adminNumber(point.value)}</td>
          </tr>)}</tbody>
        </table>
      </details>
    </>
  );
}
