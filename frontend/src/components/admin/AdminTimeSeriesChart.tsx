"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, XAxis, YAxis } from "recharts";
import type { TimeSeriesPoint } from "@/lib/admin-api/types";

export default function AdminTimeSeriesChart({ points }: { points: TimeSeriesPoint[] }) {
  return (
    <ResponsiveContainer width="100%" height={260} minWidth={0}>
      <LineChart data={points} margin={{ top: 12, right: 12, left: -18, bottom: 8 }} accessibilityLayer={false}>
        <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
        <XAxis dataKey="date" stroke="var(--color-text-muted)" fontSize={12} tickMargin={10}
          tickFormatter={(value: string) => `${value.slice(8, 10)}.${value.slice(5, 7)}`} minTickGap={28} />
        <YAxis stroke="var(--color-text-muted)" fontSize={12} allowDecimals={false} />
        <Line type="linear" dataKey="value" stroke="var(--color-accent)" strokeWidth={3}
          dot={points.length <= 7} isAnimationActive={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
