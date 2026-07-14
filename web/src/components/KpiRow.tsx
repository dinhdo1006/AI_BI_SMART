"use client";

import { formatNumber, friendlyLabel } from "@/lib/format";
import type { Forecast, PeriodComparison } from "@/lib/types";
import { analyzeColumns, metricScore } from "@/lib/viz";
import { cn } from "@/lib/utils";

const ACCENTS = ["#0f766e", "#b45309", "#1c3a4a", "#0e7490"];

const MODE_LABEL: Record<string, string> = {
  MoM: "MoM",
  QoQ: "QoQ",
  YoY: "YoY",
  half_split: "Kỳ trước",
};

function formatPct(pct: number | null | undefined): string | null {
  if (pct == null || !Number.isFinite(pct)) return null;
  const sign = pct > 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

export function KpiRow({
  data,
  labels,
  period,
  forecast,
}: {
  data: Record<string, unknown>[];
  labels?: Record<string, string>;
  period?: PeriodComparison | null;
  forecast?: Forecast | null;
}) {
  if (!data.length) return null;
  const { numeric } = analyzeColumns(data);
  const cols = [...numeric]
    .sort((a, b) => metricScore(b) - metricScore(a))
    .slice(0, 4);
  if (!cols.length) return null;

  const periodPct = formatPct(period?.pct_change);
  const periodUp = period?.direction === "up";
  const periodDown = period?.direction === "down";
  const periodMetricKey = period?.metric
    ? Object.entries(labels || {}).find(([, v]) => v === period.metric)?.[0] ||
      period.metric
    : null;

  const forecastPct = formatPct(forecast?.pct_change_to_horizon);
  const forecastUp = forecast?.direction === "up";
  const forecastDown = forecast?.direction === "down";
  const forecastLabel =
    forecast?.metric_label ||
    (forecast?.metric ? friendlyLabel(forecast.metric, labels) : "");
  const lastForecast =
    forecast?.points?.length
      ? forecast.points[forecast.points.length - 1]
      : null;

  const items = cols.map((col) => {
    const vals = data
      .map((r) => Number(r[col]))
      .filter((n) => Number.isFinite(n));
    const sum = vals.reduce((a, b) => a + b, 0);
    const avg = vals.length ? sum / vals.length : 0;
    const useSum =
      /volume|value|market_cap|von_hoa|budget|tonnage|revenue|income/i.test(
        col,
      );

    let delta: string | null = null;
    let deltaHint = "đầu→cuối kỳ";
    let up: boolean | null = null;

    const isPeriodMetric =
      period &&
      (col === periodMetricKey ||
        friendlyLabel(col, labels) === period.metric ||
        col === period.metric);

    if (isPeriodMetric && periodPct) {
      delta = periodPct;
      deltaHint = MODE_LABEL[period.mode] || period.mode;
      up = periodUp ? true : periodDown ? false : null;
    } else if (vals.length >= 2 && !useSum) {
      const first = vals[0];
      const last = vals[vals.length - 1];
      if (first !== 0) {
        const pct = ((last - first) / Math.abs(first)) * 100;
        const sign = pct > 0 ? "+" : "";
        delta = `${sign}${pct.toFixed(1)}%`;
        up = pct > 0;
      }
    }

    return {
      label: friendlyLabel(col, labels),
      value: formatNumber(useSum ? sum : avg, col),
      hint: useSum ? "Tổng" : "TB",
      delta,
      deltaHint,
      up,
    };
  });

  return (
    <div className="space-y-3">
      {period && periodPct && (
        <div
          className={cn(
            "flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2 text-sm",
            periodUp
              ? "border-teal/25 bg-teal/8 text-teal"
              : periodDown
                ? "border-copper/30 bg-copper-soft/40 text-copper"
                : "border-line bg-mist/60 text-ink-soft",
          )}
        >
          <span className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
            {MODE_LABEL[period.mode] || period.mode}
          </span>
          <span className="font-semibold">{periodPct}</span>
          <span className="text-[12px] opacity-80">
            {friendlyLabel(String(period.metric), labels)} ·{" "}
            {period.previous_period} → {period.current_period}
          </span>
        </div>
      )}
      {forecast && lastForecast && (
        <div
          className={cn(
            "flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2 text-sm",
            forecastUp
              ? "border-teal/25 bg-teal/8 text-teal"
              : forecastDown
                ? "border-copper/30 bg-copper-soft/40 text-copper"
                : "border-line bg-mist/60 text-ink-soft",
          )}
        >
          <span className="text-[11px] font-semibold uppercase tracking-wider opacity-80">
            Dự báo {forecast.horizon} kỳ
          </span>
          {forecastPct && <span className="font-semibold">{forecastPct}</span>}
          <span className="text-[12px] opacity-80">
            {forecastLabel}
            {forecast.history_end_date
              ? ` · ${forecast.history_end_date} → ${lastForecast.date}`
              : ""}
            {" · "}
            ước lượng tuyến tính
          </span>
        </div>
      )}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
        {items.map((item, i) => (
          <div
            key={item.label}
            className="relative overflow-hidden rounded-xl border border-line bg-foam/80 px-4 py-3"
          >
            <div
              className="absolute inset-x-0 top-0 h-[3px]"
              style={{ background: ACCENTS[i % ACCENTS.length] }}
            />
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft/65">
              {item.hint} · {item.label}
            </p>
            <p className="mt-1.5 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-ink">
              {item.value}
            </p>
            {item.delta && (
              <p
                className={
                  item.up === true
                    ? "mt-1 text-[11px] font-semibold text-teal"
                    : item.up === false
                      ? "mt-1 text-[11px] font-semibold text-copper"
                      : "mt-1 text-[11px] font-semibold text-ink-soft"
                }
              >
                {item.delta} ({item.deltaHint})
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
