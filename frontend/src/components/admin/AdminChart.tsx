"use client";

import dynamic from "next/dynamic";
import type { TimeSeriesPoint } from "@/lib/admin-api/types";

const TimeSeriesChart = dynamic(() => import("./AdminTimeSeriesChart"), {
  ssr: false,
  loading: () => <p className="admin-muted">Загружаем график. Значения доступны в таблице ниже.</p>,
});

/** The server-rendered table remains the accessible and no-JS equivalent. */
export function AdminChart({ points }: { points: TimeSeriesPoint[] }) {
  return <div className="admin-chart" aria-hidden="true"><TimeSeriesChart points={points} /></div>;
}
