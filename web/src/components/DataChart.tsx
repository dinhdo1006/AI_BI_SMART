"use client";

import { useCallback, useMemo, useRef } from "react";
import dynamic from "next/dynamic";
import type { EChartsType } from "echarts/core";
import type { CallbackDataParams } from "echarts/types/dist/shared";
import type { EChartsOption, SeriesOption } from "echarts";
import { Download } from "lucide-react";
import type { ChartType, Forecast } from "@/lib/types";
import { formatNumber, friendlyLabel } from "@/lib/format";
import {
  detectOhlcColumns,
  movingAverage,
  pickChartAxes,
  pickHeatmapAxes,
  pickScatterAxes,
  pickTreemapAxes,
  refineChartType,
  shouldUseHorizontalBar,
  type HeatmapAxes,
  type ScatterAxes,
  type TreemapAxes,
} from "@/lib/viz";

const ReactECharts = dynamic(() => import("echarts-for-react"), {
  ssr: false,
  loading: () => (
    <div className="flex h-[310px] items-center justify-center text-sm text-ink-soft">
      Đang tải biểu đồ…
    </div>
  ),
});

const COLORS = [
  "#0f766e",
  "#b45309",
  "#1c3a4a",
  "#0e7490",
  "#a16207",
  "#047857",
  "#57534e",
];

export type DataChartHandle = {
  getPngBase64: () => string | null;
};

export function DataChart({
  data,
  chartType,
  labels,
  forecast,
  onReady,
}: {
  data: Record<string, unknown>[];
  chartType: ChartType;
  labels?: Record<string, string>;
  forecast?: Forecast | null;
  onReady?: (getPng: () => string | null) => void;
}) {
  const chartRef = useRef<EChartsType | null>(null);
  const axes = useMemo(() => pickChartAxes(data), [data]);
  const ohlc = useMemo(() => detectOhlcColumns(data), [data]);
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

  const canShowForecast =
    !!forecast?.points?.length &&
    axes.isTimeSeries &&
    (effectiveType === "line" || effectiveType === "area");

  const heatmapAxes = useMemo(
    () =>
      effectiveType === "heatmap" ? pickHeatmapAxes(data) : null,
    [effectiveType, data],
  );
  const scatterAxes = useMemo(
    () =>
      effectiveType === "scatter" ? pickScatterAxes(data) : null,
    [effectiveType, data],
  );
  const treemapAxes = useMemo(
    () =>
      effectiveType === "treemap" ? pickTreemapAxes(data) : null,
    [effectiveType, data],
  );

  const option = useMemo(() => {
    if (effectiveType === "candlestick" && ohlc) {
      return buildCandlestickOption(data, ohlc);
    }
    if (effectiveType === "heatmap" && heatmapAxes) {
      return buildHeatmapOption(data, heatmapAxes, labels);
    }
    if (effectiveType === "scatter" && scatterAxes) {
      return buildScatterOption(data, scatterAxes, labels);
    }
    if (effectiveType === "treemap" && treemapAxes) {
      return buildTreemapOption(data, treemapAxes, labels);
    }
    if (!x || !yCols.length) return null;
    return buildOption({
      type: effectiveType,
      chartData,
      yCols,
      labels,
      horizontal,
      xLabel: friendlyLabel(x, labels),
      forecast: canShowForecast ? forecast : null,
      showMovingAvg: axes.isTimeSeries,
    });
  }, [
    effectiveType,
    chartData,
    yCols,
    labels,
    horizontal,
    x,
    ohlc,
    data,
    canShowForecast,
    forecast,
    heatmapAxes,
    scatterAxes,
    treemapAxes,
    axes.isTimeSeries,
  ]);

  const getPngBase64 = useCallback(() => {
    const inst = chartRef.current;
    if (!inst) return null;
    try {
      // pixelRatio 1.25 đủ nét, tránh body request quá lớn khi gửi API
      return inst.getDataURL({
        type: "png",
        pixelRatio: 1.25,
        backgroundColor: "#ffffff",
      });
    } catch {
      return null;
    }
  }, []);

  const onChartReady = useCallback(
    (inst: EChartsType) => {
      chartRef.current = inst;
      onReady?.(getPngBase64);
    },
    [getPngBase64, onReady],
  );

  function downloadPng() {
    const url = getPngBase64();
    if (!url) return;
    const a = document.createElement("a");
    a.href = url;
    a.download = "bieu-do.png";
    a.click();
  }

  if (effectiveType === "candlestick" && !ohlc) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Thiếu cột OHLC (open/high/low/close) để vẽ biểu đồ nến
      </div>
    );
  }

  if (effectiveType === "heatmap" && !heatmapAxes) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Cần ma trận (danh mục × ngày/metric) để vẽ heatmap
      </div>
    );
  }

  if (effectiveType === "scatter" && !scatterAxes) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Cần ≥2 cột số để vẽ biểu đồ phân tán
      </div>
    );
  }

  if (effectiveType === "treemap" && !treemapAxes) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Cần danh mục + cột số để vẽ treemap
      </div>
    );
  }

  const advancedOnly =
    effectiveType === "candlestick" ||
    effectiveType === "heatmap" ||
    effectiveType === "scatter" ||
    effectiveType === "treemap";

  if ((!x || !yCols.length) && !advancedOnly) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Không đủ cột số để vẽ biểu đồ
      </div>
    );
  }

  if (!option) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Không đủ cột số để vẽ biểu đồ
      </div>
    );
  }

  const height =
    effectiveType === "treemap" || effectiveType === "heatmap"
      ? 380
      : horizontal
        ? 340
        : 310;
  const title = chartTitle({
    effectiveType,
    ohlc,
    x,
    yCols,
    labels,
    heatmapAxes,
    scatterAxes,
    treemapAxes,
  });

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-gradient-to-br from-white via-foam/80 to-mist/40 p-3 shadow-sm">
      <div className="mb-2 flex items-center justify-between gap-2 px-1">
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-ink-soft/65">
          {title}
        </p>
        <button
          type="button"
          onClick={downloadPng}
          className="inline-flex items-center gap-1 rounded-lg border border-line bg-white/90 px-2 py-1 text-[11px] font-semibold text-ink-soft transition hover:border-teal/30 hover:text-ink"
        >
          <Download className="h-3 w-3" />
          PNG
        </button>
      </div>

      <ReactECharts
        option={option}
        style={{ height, width: "100%" }}
        opts={{ renderer: "canvas" }}
        notMerge
        lazyUpdate
        onChartReady={onChartReady}
      />
    </div>
  );
}

function chartTitle({
  effectiveType,
  ohlc,
  x,
  yCols,
  labels,
  heatmapAxes,
  scatterAxes,
  treemapAxes,
}: {
  effectiveType: ChartType;
  ohlc: ReturnType<typeof detectOhlcColumns>;
  x?: string;
  yCols: string[];
  labels?: Record<string, string>;
  heatmapAxes: HeatmapAxes | null;
  scatterAxes: ScatterAxes | null;
  treemapAxes: TreemapAxes | null;
}): string {
  if (effectiveType === "candlestick" && ohlc) {
    return `Nến · ${friendlyLabel(ohlc.close || "close", labels)}`;
  }
  if (effectiveType === "heatmap" && heatmapAxes) {
    if (heatmapAxes.mode === "pivot") {
      return `Heatmap · ${friendlyLabel(heatmapAxes.value, labels)}`;
    }
    return `Heatmap · ${heatmapAxes.metrics
      .slice(0, 3)
      .map((m) => friendlyLabel(m, labels))
      .join(" · ")}`;
  }
  if (effectiveType === "scatter" && scatterAxes) {
    return `${friendlyLabel(scatterAxes.x, labels)} × ${friendlyLabel(scatterAxes.y, labels)}`;
  }
  if (effectiveType === "treemap" && treemapAxes) {
    return `Treemap · ${friendlyLabel(treemapAxes.value, labels)}`;
  }
  return `${friendlyLabel(x || "", labels)}${
    yCols.length === 1
      ? ` · ${friendlyLabel(yCols[0], labels)}`
      : ` · ${yCols.map((c) => friendlyLabel(c, labels)).join(" · ")}`
  }`;
}

function buildHeatmapOption(
  data: Record<string, unknown>[],
  axes: HeatmapAxes,
  labels?: Record<string, string>,
): EChartsOption {
  let rowLabels: string[] = [];
  let colLabels: string[] = [];
  let cells: [number, number, number | null][] = [];
  let valueHint = "";

  if (axes.mode === "pivot") {
    valueHint = axes.value;
    const rowSet = Array.from(
      new Set(data.map((r) => String(r[axes.row] ?? ""))),
    );
    const colSet = Array.from(
      new Set(data.map((r) => formatAxisLabel(r[axes.col], axes.col))),
    );
    rowLabels = rowSet.slice(0, 40);
    colLabels = colSet.slice(0, 40);
    const lookup = new Map<string, number>();
    for (const r of data) {
      const rk = String(r[axes.row] ?? "");
      const ck = formatAxisLabel(r[axes.col], axes.col);
      const n = Number(r[axes.value]);
      if (Number.isFinite(n)) lookup.set(`${rk}||${ck}`, n);
    }
    cells = [];
    rowLabels.forEach((row, yi) => {
      colLabels.forEach((col, xi) => {
        const v = lookup.get(`${row}||${col}`);
        cells.push([xi, yi, v ?? null]);
      });
    });
  } else {
    valueHint = axes.metrics[0] || "";
    const rows = data.slice(0, 40);
    rowLabels = rows.map((r) => String(r[axes.row] ?? ""));
    colLabels = axes.metrics.map((m) => friendlyLabel(m, labels));
    cells = [];
    rows.forEach((r, yi) => {
      axes.metrics.forEach((m, xi) => {
        const n = Number(r[m]);
        cells.push([xi, yi, Number.isFinite(n) ? n : null]);
      });
    });
  }

  const nums = cells
    .map((c) => c[2])
    .filter((v): v is number => v != null && Number.isFinite(v));
  const vmin = nums.length ? Math.min(...nums) : 0;
  const vmax = nums.length ? Math.max(...nums) : 1;

  return {
    animationDuration: 700,
    tooltip: {
      position: "top",
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "rgba(11,31,42,0.1)",
      borderWidth: 1,
      textStyle: { color: "#0b1f2a", fontSize: 12 },
      formatter: (params) => {
        const p = params as {
          value?: [number, number, number | null];
          marker?: string;
        };
        const v = p.value;
        if (!v) return "";
        const col = colLabels[v[0]] ?? "";
        const row = rowLabels[v[1]] ?? "";
        return `${p.marker || ""} <b>${row}</b> · ${col}<br/>${formatNumber(v[2], valueHint)}`;
      },
    },
    grid: {
      left: 12,
      right: 72,
      top: 16,
      bottom: 48,
      containLabel: true,
    },
    xAxis: {
      type: "category",
      data: colLabels,
      splitArea: { show: true },
      axisLabel: {
        color: "#5b6b73",
        fontSize: 10,
        rotate: colLabels.length > 6 ? 30 : 0,
        interval: 0,
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "category",
      data: rowLabels,
      splitArea: { show: true },
      axisLabel: { color: "#5b6b73", fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    visualMap: {
      min: vmin,
      max: vmax === vmin ? vmin + 1 : vmax,
      calculable: true,
      orient: "vertical",
      right: 4,
      top: "middle",
      itemWidth: 12,
      itemHeight: 100,
      textStyle: { color: "#5b6b73", fontSize: 10 },
      inRange: {
        color: ["#ecfdf5", "#5eead4", "#0f766e", "#134e4a"],
      },
    },
    series: [
      {
        type: "heatmap",
        data: cells,
        label: {
          show: cells.length <= 48,
          fontSize: 9,
          color: "#0b1f2a",
          formatter: (p: CallbackDataParams) => {
            const v = Array.isArray(p.value) ? p.value[2] : p.value;
            if (v == null || !Number.isFinite(Number(v))) return "";
            return compactTick(Number(v), valueHint);
          },
        },
        emphasis: {
          itemStyle: { shadowBlur: 8, shadowColor: "rgba(0,0,0,0.2)" },
        },
      },
    ],
  };
}

function buildScatterOption(
  data: Record<string, unknown>[],
  axes: ScatterAxes,
  labels?: Record<string, string>,
): EChartsOption {
  const points = data
    .map((r) => {
      const x = Number(r[axes.x]);
      const y = Number(r[axes.y]);
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      const sizeRaw = axes.size != null ? Number(r[axes.size]) : NaN;
      const size = Number.isFinite(sizeRaw)
        ? Math.max(8, Math.min(36, Math.sqrt(Math.abs(sizeRaw)) / 2 + 8))
        : 12;
      const name = axes.label ? String(r[axes.label] ?? "") : "";
      return { value: [x, y, size], name };
    })
    .filter(Boolean) as { value: number[]; name: string }[];

  return {
    color: COLORS,
    animationDuration: 700,
    grid: { left: 16, right: 24, top: 40, bottom: 48, containLabel: true },
    tooltip: {
      trigger: "item",
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "rgba(11,31,42,0.1)",
      borderWidth: 1,
      textStyle: { color: "#0b1f2a", fontSize: 12 },
      formatter: (params) => {
        const p = params as {
          name?: string;
          value?: number[];
          marker?: string;
        };
        const v = p.value || [];
        const title = p.name ? `<b>${p.name}</b><br/>` : "";
        return `${p.marker || ""} ${title}${friendlyLabel(axes.x, labels)}: <b>${formatNumber(v[0], axes.x)}</b><br/>${friendlyLabel(axes.y, labels)}: <b>${formatNumber(v[1], axes.y)}</b>`;
      },
    },
    legend: legendOpt(labels),
    xAxis: {
      type: "value",
      name: friendlyLabel(axes.x, labels),
      nameLocation: "middle",
      nameGap: 28,
      nameTextStyle: { color: "#5b6b73", fontSize: 11 },
      scale: true,
      axisLabel: {
        color: "#5b6b73",
        fontSize: 11,
        formatter: (v: number) => compactTick(v, axes.x),
      },
      splitLine: {
        lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      name: friendlyLabel(axes.y, labels),
      nameTextStyle: { color: "#5b6b73", fontSize: 11 },
      scale: true,
      axisLabel: {
        color: "#5b6b73",
        fontSize: 11,
        formatter: (v: number) => compactTick(v, axes.y),
      },
      splitLine: {
        lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        name: axes.label
          ? friendlyLabel(axes.label, labels)
          : `${friendlyLabel(axes.x, labels)} / ${friendlyLabel(axes.y, labels)}`,
        type: "scatter",
        data: points,
        symbolSize: (val: number | number[]) =>
          Array.isArray(val) ? Number(val[2]) || 12 : 12,
        itemStyle: {
          color: hexAlpha(COLORS[0], 0.75),
          borderColor: COLORS[0],
          borderWidth: 1,
        },
        emphasis: {
          itemStyle: { color: COLORS[0], shadowBlur: 10 },
        },
        label:
          points.length <= 20
            ? {
                show: true,
                formatter: (p: CallbackDataParams) => String(p.name || ""),
                position: "top",
                fontSize: 10,
                color: "#5b6b73",
              }
            : undefined,
      },
    ],
  };
}

function buildTreemapOption(
  data: Record<string, unknown>[],
  axes: TreemapAxes,
  labels?: Record<string, string>,
): EChartsOption {
  const nodes = data
    .map((r, i) => {
      const n = Number(r[axes.value]);
      if (!Number.isFinite(n) || n <= 0) return null;
      return {
        name: String(r[axes.name] ?? `#${i + 1}`),
        value: n,
        itemStyle: { color: COLORS[i % COLORS.length] },
      };
    })
    .filter(Boolean) as {
    name: string;
    value: number;
    itemStyle: { color: string };
  }[];

  nodes.sort((a, b) => b.value - a.value);

  return {
    animationDuration: 700,
    tooltip: {
      formatter: (params) => {
        const p = params as {
          name?: string;
          value?: number;
          marker?: string;
        };
        return `${p.marker || ""} <b>${p.name}</b><br/>${formatNumber(p.value, axes.value)}`;
      },
    },
    series: [
      {
        type: "treemap",
        width: "100%",
        height: "100%",
        roam: false,
        nodeClick: false,
        breadcrumb: { show: false },
        label: {
          show: true,
          formatter: "{b}\n{c}",
          fontSize: 11,
          color: "#fff",
        },
        upperLabel: { show: false },
        itemStyle: {
          borderColor: "#fff",
          borderWidth: 2,
          gapWidth: 2,
        },
        levels: [
          {
            itemStyle: {
              borderColor: "#fff",
              borderWidth: 2,
              gapWidth: 2,
            },
          },
        ],
        data: nodes,
      },
    ],
  };
}

function buildCandlestickOption(
  data: Record<string, unknown>[],
  ohlc: NonNullable<ReturnType<typeof detectOhlcColumns>>,
): EChartsOption {
  const dateKey = ohlc.date;
  const rows = [...data];
  if (dateKey) {
    rows.sort((a, b) =>
      String(a[dateKey]).localeCompare(String(b[dateKey])),
    );
  }
  const categories = rows.map((r) =>
    dateKey
      ? formatAxisLabel(r[dateKey], dateKey)
      : String(rows.indexOf(r) + 1),
  );
  const values = rows.map((r) => [
    Number(r[ohlc.open!]) || 0,
    Number(r[ohlc.close!]) || 0,
    Number(r[ohlc.low!]) || 0,
    Number(r[ohlc.high!]) || 0,
  ]);

  return {
    animationDuration: 700,
    grid: { left: 12, right: 16, top: 28, bottom: 40, containLabel: true },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "rgba(11,31,42,0.1)",
      borderWidth: 1,
      textStyle: { color: "#0b1f2a", fontSize: 12 },
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        const p = list[0] as {
          axisValue?: string;
          value?: number[];
        };
        const v = p.value || [];
        return `<b>${p.axisValue || ""}</b><br/>Mở: ${formatNumber(v[1], ohlc.open!)}<br/>Đóng: ${formatNumber(v[2], ohlc.close!)}<br/>Thấp: ${formatNumber(v[3], ohlc.low!)}<br/>Cao: ${formatNumber(v[4], ohlc.high!)}`;
      },
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: { color: "#5b6b73", fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: {
        color: "#5b6b73",
        fontSize: 11,
        formatter: (v: number) => compactTick(v, ohlc.close!),
      },
      splitLine: {
        lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        type: "candlestick",
        data: values,
        itemStyle: {
          color: "#0f766e",
          color0: "#b45309",
          borderColor: "#0f766e",
          borderColor0: "#b45309",
        },
      },
    ],
  };
}

function buildOption({
  type,
  chartData,
  yCols,
  labels,
  horizontal,
  xLabel,
  forecast,
  showMovingAvg = false,
}: {
  type: ChartType;
  chartData: Record<string, unknown>[];
  yCols: string[];
  labels?: Record<string, string>;
  horizontal: boolean;
  xLabel: string;
  forecast?: Forecast | null;
  showMovingAvg?: boolean;
}): EChartsOption {
  const forecastPts = forecast?.points || [];
  const forecastMetric = forecast?.metric;
  const useForecast =
    !horizontal &&
    forecastPts.length > 0 &&
    !!forecastMetric &&
    yCols.includes(forecastMetric) &&
    (type === "line" || type === "area");

  const categories = [
    ...chartData.map((d) => String(d.name ?? "")),
    ...(useForecast
      ? forecastPts.map((p) => formatAxisLabel(p.date, forecast?.date_col || "date"))
      : []),
  ];
  const showLabels = chartData.length <= 10;
  const tip = sharedTooltip(labels);

  if (type === "pie") {
    const pieY = yCols[0];
    return {
      color: COLORS,
      tooltip: {
        trigger: "item",
        backgroundColor: "rgba(255,255,255,0.96)",
        borderColor: "rgba(11,31,42,0.1)",
        borderWidth: 1,
        textStyle: { color: "#0b1f2a", fontSize: 12 },
        formatter: (params) => {
          const p = params as {
            name?: string;
            value?: number;
            percent?: number;
            marker?: string;
          };
          return `${p.marker || ""} <b>${p.name}</b><br/>${formatNumber(p.value, pieY)} (${(p.percent ?? 0).toFixed(1)}%)`;
        },
      },
      legend: {
        bottom: 0,
        textStyle: { color: "#5b6b73", fontSize: 11 },
      },
      series: [
        {
          type: "pie",
          radius: ["42%", "68%"],
          center: ["50%", "46%"],
          avoidLabelOverlap: true,
          itemStyle: {
            borderRadius: 6,
            borderColor: "#fff",
            borderWidth: 2,
          },
          label: {
            formatter: "{b}\n{d}%",
            fontSize: 11,
            color: "#5b6b73",
          },
          data: chartData.map((d, i) => ({
            name: String(d.name ?? ""),
            value: Number(d[pieY]) || 0,
            itemStyle: { color: COLORS[i % COLORS.length] },
          })),
        },
      ],
    };
  }

  const isCombo = type === "combo" && yCols.length >= 2;
  const chartKind =
    type === "combo" && yCols.length < 2
      ? "bar"
      : type === "combo"
        ? "combo"
        : type;

  const axisLabel = {
    color: "#5b6b73",
    fontSize: 11,
  };

  const baseGrid = horizontal
    ? { left: 88, right: 28, top: 36, bottom: 28, containLabel: false }
    : {
        left: 12,
        right: isCombo ? 48 : 16,
        top: 40,
        bottom: 48,
        containLabel: true,
      };

  const series = buildSeries({
    kind: chartKind === "combo" ? "combo" : chartKind,
    chartData,
    yCols,
    labels,
    horizontal,
    showLabels,
    isCombo,
    forecast: useForecast ? forecast : null,
    showMovingAvg: showMovingAvg && !horizontal && !isCombo,
  });

  if (horizontal) {
    return {
      color: COLORS,
      animationDuration: 700,
      grid: baseGrid,
      tooltip: tip,
      legend: legendOpt(labels),
      xAxis: {
        type: "value",
        axisLabel: {
          ...axisLabel,
          formatter: (v: number) => compactTick(v, yCols[0]),
        },
        splitLine: {
          lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      yAxis: {
        type: "category",
        data: categories,
        axisLabel,
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series,
    };
  }

  return {
    color: COLORS,
    animationDuration: 700,
    grid: baseGrid,
    tooltip: tip,
    legend: legendOpt(labels),
    xAxis: {
      type: "category",
      data: categories,
      name: xLabel,
      nameLocation: "middle",
      nameGap: 28,
      nameTextStyle: { color: "#5b6b73", fontSize: 10, opacity: 0 },
      axisLabel: {
        ...axisLabel,
        rotate: categories.length > 8 ? 30 : 0,
        interval: 0,
        hideOverlap: true,
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: isCombo
      ? [
          {
            type: "value",
            scale: true,
            axisLabel: {
              ...axisLabel,
              formatter: (v: number) => compactTick(v, yCols[0]),
            },
            splitLine: {
              lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
            },
            axisLine: { show: false },
            axisTick: { show: false },
          },
          {
            type: "value",
            scale: true,
            axisLabel: {
              ...axisLabel,
              formatter: (v: number) => compactTick(v, yCols[1]),
            },
            splitLine: { show: false },
            axisLine: { show: false },
            axisTick: { show: false },
          },
        ]
      : {
          type: "value",
          scale: true,
          axisLabel: {
            ...axisLabel,
            formatter: (v: number) => compactTick(v, yCols[0]),
          },
          splitLine: {
            lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
          },
          axisLine: { show: false },
          axisTick: { show: false },
        },
    series,
  };
}

function buildSeries({
  kind,
  chartData,
  yCols,
  labels,
  horizontal,
  showLabels,
  isCombo,
  forecast,
  showMovingAvg = false,
}: {
  kind: ChartType | "combo";
  chartData: Record<string, unknown>[];
  yCols: string[];
  labels?: Record<string, string>;
  horizontal: boolean;
  showLabels: boolean;
  isCombo: boolean;
  forecast?: Forecast | null;
  showMovingAvg?: boolean;
}): SeriesOption[] {
  const fcPts = forecast?.points || [];
  const fcMetric = forecast?.metric;
  const padNulls = (n: number) => Array.from({ length: n }, () => null as null);
  const histLen = chartData.length;
  const fcLen = fcPts.length;

  if (isCombo) {
    const barCol = yCols[0];
    const lineCol = yCols[1];
    return [
      {
        name: friendlyLabel(barCol, labels),
        type: "bar",
        yAxisIndex: 0,
        data: chartData.map((d) => d[barCol] as number | null),
        barMaxWidth: 48,
        itemStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: COLORS[0] },
              { offset: 1, color: "#0d9488" },
            ],
          },
          borderRadius: [6, 6, 0, 0],
        },
        label: showLabels
          ? {
              show: true,
              position: "top",
              fontSize: 10,
              color: "#5b6b73",
              formatter: (p: CallbackDataParams) =>
                formatNumber(paramValue(p), barCol),
            }
          : undefined,
      },
      {
        name: friendlyLabel(lineCol, labels),
        type: "line",
        yAxisIndex: 1,
        data: chartData.map((d) => d[lineCol] as number | null),
        smooth: true,
        symbol: "circle",
        symbolSize: 7,
        showSymbol: chartData.length <= 24,
        lineStyle: { width: 2.6, color: COLORS[1] },
        itemStyle: { color: COLORS[1] },
        label: showLabels
          ? {
              show: true,
              position: "top",
              fontSize: 10,
              color: COLORS[1],
              formatter: (p: CallbackDataParams) =>
                formatNumber(paramValue(p), lineCol),
            }
          : undefined,
      },
    ];
  }

  if (kind === "line" || kind === "area") {
    const series: SeriesOption[] = yCols.map((y, i) => {
      const color = COLORS[i % COLORS.length];
      const hist = chartData.map((d) => d[y] as number | null);
      const dataVals =
        fcMetric && y === fcMetric && fcLen
          ? [...hist, ...padNulls(fcLen)]
          : hist;
      return {
        name: friendlyLabel(y, labels),
        type: "line" as const,
        data: dataVals,
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        showSymbol: showLabels || chartData.length <= 24,
        emphasis: { focus: "series" as const },
        lineStyle: { width: 2.4, color },
        itemStyle: { color },
        areaStyle:
          kind === "area"
            ? {
                color: {
                  type: "linear" as const,
                  x: 0,
                  y: 0,
                  x2: 0,
                  y2: 1,
                  colorStops: [
                    { offset: 0, color: hexAlpha(color, 0.4) },
                    { offset: 1, color: hexAlpha(color, 0.02) },
                  ],
                },
              }
            : undefined,
        label: showLabels
          ? {
              show: true,
              position: "top" as const,
              fontSize: 10,
              color: "#5b6b73",
              formatter: (p: CallbackDataParams) =>
                formatNumber(paramValue(p), y),
            }
          : undefined,
      };
    });

    if (fcMetric && yCols.includes(fcMetric) && fcLen) {
      const lastHist = Number(chartData[histLen - 1]?.[fcMetric]);
      const bridge = Number.isFinite(lastHist) ? lastHist : null;
      const color = "#b45309";
      series.push({
        name: "Dự báo",
        type: "line",
        data: [
          ...padNulls(Math.max(0, histLen - 1)),
          bridge,
          ...fcPts.map((p) => p.value),
        ],
        smooth: false,
        symbol: "diamond",
        symbolSize: 7,
        showSymbol: true,
        lineStyle: { width: 2.2, type: "dashed", color },
        itemStyle: { color },
        z: 5,
      });
    }

    // MA overlay trên chuỗi thời gian (đủ điểm)
    if (showMovingAvg && histLen >= 10 && !fcLen) {
      const maWindow = histLen >= 30 ? 10 : 5;
      const primary = yCols[0];
      const hist = chartData.map((d) => d[primary] as number | null);
      const ma = movingAverage(hist, maWindow);
      series.push({
        name: `MA${maWindow}`,
        type: "line",
        data: ma,
        smooth: true,
        symbol: "none",
        lineStyle: { width: 2, type: "dashed", color: "#b45309" },
        itemStyle: { color: "#b45309" },
        z: 4,
      });
    }

    return series;
  }

  // bar (default)
  return yCols.map((y, i) => {
    const color = COLORS[i % COLORS.length];
    return {
      name: friendlyLabel(y, labels),
      type: "bar" as const,
      data: chartData.map((d) => d[y] as number | null),
      barMaxWidth: horizontal ? 22 : 48,
      barGap: "12%",
      itemStyle: {
        color: {
          type: "linear" as const,
          x: 0,
          y: 0,
          x2: horizontal ? 1 : 0,
          y2: horizontal ? 0 : 1,
          colorStops: [
            { offset: 0, color },
            { offset: 1, color: shade(color, -12) },
          ],
        },
        borderRadius: horizontal ? [0, 6, 6, 0] : [6, 6, 0, 0],
      },
      label: showLabels
        ? {
            show: true,
            position: horizontal ? ("right" as const) : ("top" as const),
            fontSize: 10,
            color: "#5b6b73",
            formatter: (p: CallbackDataParams) =>
              formatNumber(paramValue(p), y),
          }
        : undefined,
    };
  });
}

function paramValue(p: CallbackDataParams): unknown {
  const v = p.value;
  if (Array.isArray(v)) return v[v.length - 1];
  return v;
}

function sharedTooltip(
  labels?: Record<string, string>,
): EChartsOption["tooltip"] {
  return {
    trigger: "axis",
    backgroundColor: "rgba(255,255,255,0.96)",
    borderColor: "rgba(11,31,42,0.1)",
    borderWidth: 1,
    textStyle: { color: "#0b1f2a", fontSize: 12 },
    axisPointer: { type: "shadow" },
    formatter: (params) => {
      const list = Array.isArray(params) ? params : [params];
      if (!list.length) return "";
      const title = String(
        (list[0] as { axisValueLabel?: string; name?: string }).axisValueLabel ||
          (list[0] as { name?: string }).name ||
          "",
      );
      const rows = list
        .map((p) => {
          const item = p as {
            marker?: string;
            seriesName?: string;
            value?: number | null;
          };
          const key = item.seriesName || "";
          return `${item.marker || ""} ${friendlyLabel(key, labels)}: <b>${formatNumber(item.value, key)}</b>`;
        })
        .join("<br/>");
      return `<div style="margin-bottom:4px;font-weight:600">${title}</div>${rows}`;
    },
  };
}

function legendOpt(labels?: Record<string, string>): EChartsOption["legend"] {
  return {
    top: 0,
    textStyle: { color: "#5b6b73", fontSize: 11 },
    formatter: (name) => friendlyLabel(name, labels),
  };
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
  if (Math.abs(v) >= 10_000)
    return v.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
  if (/roe|roa|pct|percent/i.test(colHint)) return `${v}`;
  return String(Number(v.toPrecision(3)));
}

function hexAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function shade(hex: string, percent: number): string {
  const h = hex.replace("#", "");
  const num = parseInt(h, 16);
  const amt = Math.round(2.55 * percent);
  const r = Math.min(255, Math.max(0, (num >> 16) + amt));
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0xff) + amt));
  const b = Math.min(255, Math.max(0, (num & 0xff) + amt));
  return `#${((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1)}`;
}
