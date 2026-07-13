"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ComposedChart,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartType } from "@/lib/types";
import { formatNumber, friendlyLabel } from "@/lib/format";
import { pickChartAxes } from "@/lib/viz";

const COLORS = ["#0f766e", "#b45309", "#1c3a4a", "#0e7490", "#78716c", "#047857"];

export function DataChart({
  data,
  chartType,
  labels,
}: {
  data: Record<string, unknown>[];
  chartType: ChartType;
  labels?: Record<string, string>;
}) {
  const { x, yCols } = useMemo(() => pickChartAxes(data), [data]);
  const chartData = useMemo(() => {
    return data.map((row) => {
      const point: Record<string, unknown> = {
        name: String(row[x] ?? ""),
      };
      for (const y of yCols) {
        const n = Number(row[y]);
        point[y] = Number.isFinite(n) ? n : null;
      }
      return point;
    });
  }, [data, x, yCols]);

  if (!x || !yCols.length) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Không đủ cột số để vẽ biểu đồ
      </div>
    );
  }

  const tip = {
    contentStyle: {
      borderRadius: 12,
      border: "1px solid rgba(11,31,42,0.1)",
      background: "#fff",
      fontSize: 12,
    },
    formatter: ((value: number, name: string) => [
      formatNumber(value, name),
      friendlyLabel(name, labels),
    ]) as never,
  };

  return (
    <div className="min-h-[320px] rounded-xl border border-line bg-foam/40 p-3">
      <ResponsiveContainer width="100%" height={300}>
        {chartType === "pie" ? (
          <PieChart>
            <Pie
              data={chartData}
              dataKey={yCols[0]}
              nameKey="name"
              cx="50%"
              cy="50%"
              outerRadius={100}
              label={({ name }) => String(name).slice(0, 10)}
            >
              {chartData.map((_, i) => (
                <Cell key={i} fill={COLORS[i % COLORS.length]} />
              ))}
            </Pie>
            <Tooltip {...tip} />
            <Legend />
          </PieChart>
        ) : chartType === "line" ? (
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,42,0.08)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip {...tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            {yCols.map((y, i) => (
              <Line
                key={y}
                type="monotone"
                dataKey={y}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2.2}
                dot={false}
              />
            ))}
          </LineChart>
        ) : chartType === "area" ? (
          <AreaChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,42,0.08)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip {...tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            {yCols.map((y, i) => (
              <Area
                key={y}
                type="monotone"
                dataKey={y}
                stroke={COLORS[i % COLORS.length]}
                fill={COLORS[i % COLORS.length]}
                fillOpacity={0.18}
              />
            ))}
          </AreaChart>
        ) : chartType === "combo" && yCols.length >= 2 ? (
          <ComposedChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,42,0.08)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
            <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 11 }} />
            <Tooltip {...tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            <Bar
              yAxisId="left"
              dataKey={yCols[0]}
              fill={COLORS[0]}
              radius={[4, 4, 0, 0]}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey={yCols[1]}
              stroke={COLORS[1]}
              strokeWidth={2.2}
              dot={false}
            />
          </ComposedChart>
        ) : (
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(11,31,42,0.08)" />
            <XAxis dataKey="name" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip {...tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            {yCols.map((y, i) => (
              <Bar
                key={y}
                dataKey={y}
                fill={COLORS[i % COLORS.length]}
                radius={[4, 4, 0, 0]}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}
