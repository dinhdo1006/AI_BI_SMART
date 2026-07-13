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
import {
  pickChartAxes,
  refineChartType,
  shouldUseHorizontalBar,
} from "@/lib/viz";

const COLORS = [
  "#0f766e",
  "#b45309",
  "#1c3a4a",
  "#0e7490",
  "#a16207",
  "#047857",
  "#57534e",
];

function ChartTooltip({
  active,
  payload,
  label,
  labels,
}: {
  active?: boolean;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  payload?: readonly any[];
  label?: string | number;
  labels?: Record<string, string>;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-line bg-white/95 px-3 py-2.5 shadow-lg backdrop-blur">
      <p className="mb-1.5 text-xs font-semibold text-ink">{String(label ?? "")}</p>
      <ul className="space-y-1">
        {payload.map((p) => {
          const key = String(p.dataKey || p.name || "");
          return (
            <li
              key={key}
              className="flex items-center justify-between gap-6 text-[12px]"
            >
              <span className="flex items-center gap-2 text-ink-soft">
                <span
                  className="h-2 w-2 rounded-sm"
                  style={{ background: p.color || COLORS[0] }}
                />
                {friendlyLabel(key, labels)}
              </span>
              <span className="font-semibold tabular-nums text-ink">
                {formatNumber(p.value, key)}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export function DataChart({
  data,
  chartType,
  labels,
}: {
  data: Record<string, unknown>[];
  chartType: ChartType;
  labels?: Record<string, string>;
}) {
  const axes = useMemo(() => pickChartAxes(data), [data]);
  const effectiveType = useMemo(
    () => refineChartType(chartType, data),
    [chartType, data],
  );
  const { x, yCols } = axes;

  const chartData = useMemo(() => {
    const rows = [...data];
    if (axes.isTimeSeries && x) {
      rows.sort((a, b) => String(a[x]).localeCompare(String(b[x])));
    }
    return rows.map((row) => {
      const point: Record<string, unknown> = {
        name: formatAxisLabel(row[x], x),
      };
      for (const y of yCols) {
        const n = Number(row[y]);
        point[y] = Number.isFinite(n) ? n : null;
      }
      return point;
    });
  }, [data, x, yCols, axes.isTimeSeries]);

  const horizontal =
    effectiveType === "bar" &&
    !axes.isTimeSeries &&
    shouldUseHorizontalBar(data, x);

  if (!x || !yCols.length) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Không đủ cột số để vẽ biểu đồ
      </div>
    );
  }

  const tip = (props: Record<string, unknown>) => (
    <ChartTooltip {...props} labels={labels} />
  );

  const axisTick = { fill: "#5b6b73", fontSize: 11 };
  const grid = { stroke: "rgba(11,31,42,0.07)", strokeDasharray: "4 6" };

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-gradient-to-br from-white via-foam/80 to-mist/40 p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-soft/65">
          {friendlyLabel(x, labels)}
          {yCols.length === 1
            ? ` · ${friendlyLabel(yCols[0], labels)}`
            : ` · ${yCols.map((c) => friendlyLabel(c, labels)).join(" · ")}`}
        </p>
      </div>

      <ResponsiveContainer width="100%" height={horizontal ? 340 : 310}>
        {effectiveType === "pie" ? (
          <PieChart>
            <Pie
              data={chartData}
              dataKey={yCols[0]}
              nameKey="name"
              cx="50%"
              cy="50%"
              innerRadius={52}
              outerRadius={100}
              paddingAngle={2}
              label={({ name, percent }) =>
                `${String(name).slice(0, 8)} ${((percent || 0) * 100).toFixed(0)}%`
              }
            >
              {chartData.map((_, i) => (
                <Cell
                  key={i}
                  fill={COLORS[i % COLORS.length]}
                  stroke="#fff"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={tip} />
            <Legend />
          </PieChart>
        ) : effectiveType === "line" ? (
          <LineChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
            <CartesianGrid {...grid} vertical={false} />
            <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
            <YAxis
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => compactTick(v, yCols[0])}
              width={52}
            />
            <Tooltip content={tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            {yCols.map((y, i) => (
              <Line
                key={y}
                type="monotone"
                dataKey={y}
                stroke={COLORS[i % COLORS.length]}
                strokeWidth={2.4}
                dot={{ r: 3, strokeWidth: 0 }}
                activeDot={{ r: 5 }}
              />
            ))}
          </LineChart>
        ) : effectiveType === "area" ? (
          <AreaChart data={chartData} margin={{ top: 8, right: 12, left: 0, bottom: 4 }}>
            <defs>
              {yCols.map((y, i) => (
                <linearGradient key={y} id={`fill-${i}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={COLORS[i % COLORS.length]} stopOpacity={0.02} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid {...grid} vertical={false} />
            <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
            <YAxis
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => compactTick(v, yCols[0])}
              width={52}
            />
            <Tooltip content={tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            {yCols.map((y, i) => (
              <Area
                key={y}
                type="monotone"
                dataKey={y}
                stroke={COLORS[i % COLORS.length]}
                fill={`url(#fill-${i})`}
                strokeWidth={2.2}
              />
            ))}
          </AreaChart>
        ) : effectiveType === "combo" && yCols.length >= 2 ? (
          <ComposedChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }}>
            <CartesianGrid {...grid} vertical={false} />
            <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
            <YAxis
              yAxisId="left"
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => compactTick(v, yCols[0])}
              width={52}
            />
            <YAxis
              yAxisId="right"
              orientation="right"
              tick={axisTick}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => compactTick(v, yCols[1])}
              width={52}
            />
            <Tooltip content={tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            <Bar
              yAxisId="left"
              dataKey={yCols[0]}
              fill={COLORS[0]}
              radius={[6, 6, 0, 0]}
              maxBarSize={42}
            />
            <Line
              yAxisId="right"
              type="monotone"
              dataKey={yCols[1]}
              stroke={COLORS[1]}
              strokeWidth={2.4}
              dot={{ r: 3, strokeWidth: 0 }}
            />
          </ComposedChart>
        ) : (
          <BarChart
            data={chartData}
            layout={horizontal ? "vertical" : "horizontal"}
            margin={{ top: 8, right: 12, left: horizontal ? 8 : 0, bottom: 4 }}
            barCategoryGap="18%"
            barGap={4}
          >
            <CartesianGrid {...grid} horizontal={!horizontal} vertical={horizontal} />
            {horizontal ? (
              <>
                <XAxis
                  type="number"
                  tick={axisTick}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => compactTick(v, yCols[0])}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={axisTick}
                  axisLine={false}
                  tickLine={false}
                  width={72}
                />
              </>
            ) : (
              <>
                <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
                <YAxis
                  tick={axisTick}
                  axisLine={false}
                  tickLine={false}
                  tickFormatter={(v) => compactTick(v, yCols[0])}
                  width={52}
                />
              </>
            )}
            <Tooltip content={tip} />
            <Legend formatter={(v) => friendlyLabel(String(v), labels)} />
            {yCols.map((y, i) => (
              <Bar
                key={y}
                dataKey={y}
                fill={COLORS[i % COLORS.length]}
                radius={horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0]}
                maxBarSize={horizontal ? 22 : 48}
              />
            ))}
          </BarChart>
        )}
      </ResponsiveContainer>
    </div>
  );
}

function formatAxisLabel(value: unknown, col: string): string {
  if (value == null) return "";
  const s = String(value);
  if (/date|ngay/i.test(col) && /^\d{4}-\d{2}-\d{2}/.test(s)) {
    return s.slice(0, 10);
  }
  return s.length > 18 ? `${s.slice(0, 16)}…` : s;
}

function compactTick(v: number, colHint: string): string {
  if (!Number.isFinite(v)) return "";
  if (Math.abs(v) >= 1_000_000_000) return `${(v / 1_000_000_000).toFixed(1)}tỷ`;
  if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}tr`;
  if (Math.abs(v) >= 10_000) return v.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
  if (/roe|roa|pct|percent/i.test(colHint)) return `${v}`;
  return String(Number(v.toPrecision(3)));
}
