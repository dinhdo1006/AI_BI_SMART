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
  aggregatePieChartData,
  buildChartDensityInfo,
  buildHeatmapRowLabel,
  CHART_DENSE_THRESHOLDS,
  detectHeatmapDisambiguator,
  detectOhlcColumns,
  movingAverage,
  pickChartAxes,
  pickHeatmapAxes,
  pickRadarAxes,
  pickScatterAxes,
  pickTreemapAxes,
  pickWaterfallAxes,
  refineChartType,
  shouldUseHorizontalBar,
  type ChartDensityInfo,
  type HeatmapAxes,
  type RadarAxes,
  type ScatterAxes,
  type TreemapAxes,
  type WaterfallAxes,
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
  const radarAxes = useMemo(
    () => (effectiveType === "radar" ? pickRadarAxes(data) : null),
    [effectiveType, data],
  );
  const waterfallAxes = useMemo(
    () =>
      effectiveType === "waterfall" ? pickWaterfallAxes(data) : null,
    [effectiveType, data],
  );

  const densityInfo = useMemo((): ChartDensityInfo | null => {
    const total = data.length;
    if (!total) return null;

    if (effectiveType === "heatmap" && heatmapAxes) {
      const rowKey =
        heatmapAxes.mode === "pivot" ? heatmapAxes.row : heatmapAxes.row;
      const colKey =
        heatmapAxes.mode === "pivot"
          ? heatmapAxes.col
          : heatmapAxes.metrics[0];
      const rowCount = new Set(data.map((r) => String(r[rowKey] ?? ""))).size;
      const colCount =
        heatmapAxes.mode === "pivot"
          ? new Set(data.map((r) => String(r[colKey] ?? ""))).size
          : heatmapAxes.metrics.length;
      const displayedRows = Math.min(rowCount, CHART_DENSE_THRESHOLDS.heatmapMaxDim);
      const displayedCols = Math.min(colCount, CHART_DENSE_THRESHOLDS.heatmapMaxDim);
      const truncated =
        rowCount > CHART_DENSE_THRESHOLDS.heatmapMaxDim ||
        colCount > CHART_DENSE_THRESHOLDS.heatmapMaxDim;
      const needsZoom =
        rowCount > CHART_DENSE_THRESHOLDS.heatmapZoomDim ||
        colCount > CHART_DENSE_THRESHOLDS.heatmapZoomDim;
      return buildChartDensityInfo(Math.max(rowCount, colCount), Math.max(displayedRows, displayedCols), {
        truncated,
        needsZoom,
        extra:
          heatmapAxes.mode === "metrics"
            ? "Màu chuẩn hóa riêng từng chỉ số — hover để xem giá trị thật"
            : undefined,
      });
    }

    if (effectiveType === "pie") {
      const aggregated = total > CHART_DENSE_THRESHOLDS.pieMaxSlices;
      return buildChartDensityInfo(total, aggregated ? CHART_DENSE_THRESHOLDS.pieMaxSlices : total, {
        truncated: aggregated,
        extra: aggregated ? "Các mục nhỏ đã gom vào \"Khác\"" : undefined,
      });
    }

    if (effectiveType === "scatter") {
      return buildChartDensityInfo(total, total, {
        needsZoom: total > CHART_DENSE_THRESHOLDS.scatterLarge,
        extra:
          total > CHART_DENSE_THRESHOLDS.scatterLarge
            ? "Chế độ render nhanh đang bật"
            : undefined,
      });
    }

    const zoomable =
      effectiveType === "line" ||
      effectiveType === "area" ||
      effectiveType === "bar" ||
      effectiveType === "combo" ||
      effectiveType === "candlestick" ||
      effectiveType === "waterfall";

    if (zoomable) {
      return buildChartDensityInfo(total, total, {
        needsZoom: total > CHART_DENSE_THRESHOLDS.dataZoom,
      });
    }

    return null;
  }, [data, effectiveType, heatmapAxes]);

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
    if (effectiveType === "radar" && radarAxes) {
      return buildRadarOption(data, radarAxes, labels);
    }
    if (effectiveType === "waterfall" && waterfallAxes) {
      return buildWaterfallOption(data, waterfallAxes, labels);
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
      isTimeSeries: axes.isTimeSeries,
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
    radarAxes,
    waterfallAxes,
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

  if (effectiveType === "radar" && !radarAxes) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Radar cần ≥3 chỉ số số và vài mã để so sánh
      </div>
    );
  }

  if (effectiveType === "waterfall" && !waterfallAxes) {
    return (
      <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-line bg-foam/50 text-sm text-ink-soft">
        Waterfall cần danh mục + 1 cột số
      </div>
    );
  }

  const advancedOnly =
    effectiveType === "candlestick" ||
    effectiveType === "heatmap" ||
    effectiveType === "scatter" ||
    effectiveType === "treemap" ||
    effectiveType === "radar" ||
    effectiveType === "waterfall";

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

  const pointCount = chartData.length;
  const hasDataZoom =
    !!densityInfo?.needsZoom &&
    (effectiveType === "line" ||
      effectiveType === "area" ||
      effectiveType === "bar" ||
      effectiveType === "combo" ||
      effectiveType === "candlestick" ||
      effectiveType === "waterfall" ||
      effectiveType === "heatmap");

  const height =
    effectiveType === "treemap" ||
    effectiveType === "heatmap" ||
    effectiveType === "radar" ||
    effectiveType === "candlestick"
      ? hasDataZoom
        ? 420
        : 380
      : horizontal
        ? Math.min(
            CHART_DENSE_THRESHOLDS.horizontalBarMaxHeight,
            Math.max(
              CHART_DENSE_THRESHOLDS.horizontalBarMinHeight,
              72 + pointCount * CHART_DENSE_THRESHOLDS.horizontalBarRowHeight,
            ),
          )
        : hasDataZoom
          ? 360
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
    radarAxes,
    waterfallAxes,
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

      {densityInfo?.message && (
        <div
          className={`mb-2 rounded-lg border px-3 py-2 text-[11px] leading-relaxed ${
            densityInfo.truncated
              ? "border-copper/30 bg-copper-soft/30 text-copper"
              : "border-teal/20 bg-teal/5 text-ink-soft"
          }`}
        >
          {densityInfo.message}
        </div>
      )}

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
  radarAxes,
  waterfallAxes,
}: {
  effectiveType: ChartType;
  ohlc: ReturnType<typeof detectOhlcColumns>;
  x?: string;
  yCols: string[];
  labels?: Record<string, string>;
  heatmapAxes: HeatmapAxes | null;
  scatterAxes: ScatterAxes | null;
  treemapAxes: TreemapAxes | null;
  radarAxes: RadarAxes | null;
  waterfallAxes: WaterfallAxes | null;
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
      .join(" · ")} (chuẩn hóa)`;
  }
  if (effectiveType === "scatter" && scatterAxes) {
    return `${friendlyLabel(scatterAxes.x, labels)} × ${friendlyLabel(scatterAxes.y, labels)}`;
  }
  if (effectiveType === "treemap" && treemapAxes) {
    return `Treemap · ${friendlyLabel(treemapAxes.value, labels)}`;
  }
  if (effectiveType === "radar" && radarAxes) {
    return `Radar · ${radarAxes.metrics
      .slice(0, 3)
      .map((m) => friendlyLabel(m, labels))
      .join(" · ")}`;
  }
  if (effectiveType === "waterfall" && waterfallAxes) {
    return `Waterfall · ${friendlyLabel(waterfallAxes.value, labels)}`;
  }
  if (!x || !yCols.length) return "Biểu đồ";
  if (yCols.length === 1) {
    return `${friendlyLabel(yCols[0], labels)} theo ${friendlyLabel(x, labels)}`;
  }
  return `${yCols
    .slice(0, 2)
    .map((c) => friendlyLabel(c, labels))
    .join(" · ")}`;
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
  const maxDim = CHART_DENSE_THRESHOLDS.heatmapMaxDim;
  const metricsNormalized = axes.mode === "metrics";
  const rawValues = new Map<string, { value: number; metricKey: string }>();

  if (axes.mode === "pivot") {
    valueHint = axes.value;
    const rowSet = Array.from(
      new Set(data.map((r) => String(r[axes.row] ?? ""))),
    );
    const colSet = Array.from(
      new Set(data.map((r) => formatAxisLabel(r[axes.col], axes.col))),
    );
    rowLabels = rowSet.slice(0, maxDim);
    colLabels = colSet.slice(0, maxDim);
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
    const rows = data.slice(0, maxDim);
    const disambiguator = detectHeatmapDisambiguator(
      rows,
      axes.row,
      axes.metrics,
    );
    rowLabels = rows.map((r) =>
      buildHeatmapRowLabel(r, axes.row, disambiguator),
    );
    colLabels = axes.metrics.map((m) => friendlyLabel(m, labels));
    const colStats = axes.metrics.map((m) => {
      const colVals = rows
        .map((row) => Number(row[m]))
        .filter((n) => Number.isFinite(n));
      const cmin = colVals.length ? Math.min(...colVals) : 0;
      const cmax = colVals.length ? Math.max(...colVals) : 1;
      return { min: cmin, max: cmax, span: cmax - cmin || 1 };
    });
    cells = [];
    rows.forEach((r, yi) => {
      axes.metrics.forEach((m, xi) => {
        const raw = Number(r[m]);
        if (!Number.isFinite(raw)) {
          cells.push([xi, yi, null]);
          return;
        }
        const { min: cmin, span } = colStats[xi];
        const norm = ((raw - cmin) / span) * 100;
        cells.push([xi, yi, norm]);
        rawValues.set(`${xi}-${yi}`, { value: raw, metricKey: m });
      });
    });
  }

  const nums = cells
    .map((c) => c[2])
    .filter((v): v is number => v != null && Number.isFinite(v));
  const vmin = metricsNormalized ? 0 : nums.length ? Math.min(...nums) : 0;
  const vmax = metricsNormalized
    ? 100
    : nums.length
      ? Math.max(...nums)
      : 1;
  const dense =
    rowLabels.length > CHART_DENSE_THRESHOLDS.heatmapZoomDim ||
    colLabels.length > CHART_DENSE_THRESHOLDS.heatmapZoomDim;
  const dataZoom = dense
    ? [
        {
          type: "inside" as const,
          xAxisIndex: 0,
          yAxisIndex: 0,
          zoomOnMouseWheel: true,
          moveOnMouseMove: true,
        },
        {
          type: "slider" as const,
          xAxisIndex: 0,
          bottom: 4,
          height: 16,
          brushSelect: false,
        },
        {
          type: "slider" as const,
          yAxisIndex: 0,
          right: 4,
          width: 16,
          brushSelect: false,
        },
      ]
    : undefined;

  return {
    animationDuration: 700,
    ...(dataZoom ? { dataZoom } : {}),
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
        const raw = rawValues.get(`${v[0]}-${v[1]}`);
        const displayVal = raw
          ? formatNumber(raw.value, raw.metricKey)
          : formatNumber(v[2], valueHint);
        const normHint = metricsNormalized && raw
          ? `<br/><span style="opacity:0.7">Màu: ${Math.round(v[2] ?? 0)}% trong cột</span>`
          : "";
        return `${p.marker || ""} <b>${row}</b> · ${col}<br/>${displayVal}${normHint}`;
      },
    },
    grid: {
      left: 12,
      right: dense ? 88 : 72,
      top: 16,
      bottom: dense ? 64 : 48,
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
        interval: dense ? ("auto" as const) : 0,
        hideOverlap: true,
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
      formatter: metricsNormalized
        ? (v: number) => `${Math.round(v)}%`
        : undefined,
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
            const v = Array.isArray(p.value) ? p.value : null;
            if (!v || v[2] == null || !Number.isFinite(Number(v[2]))) return "";
            const raw = rawValues.get(`${v[0]}-${v[1]}`);
            if (raw) return compactTick(raw.value, raw.metricKey);
            return compactTick(Number(v[2]), valueHint);
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
        large: points.length > CHART_DENSE_THRESHOLDS.scatterLarge,
        largeThreshold: CHART_DENSE_THRESHOLDS.scatterLarge,
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

  const volKey = Object.keys(data[0] || {}).find((c) =>
    /volume|khoi_luong|khối lượng/i.test(c),
  );
  const volumes = volKey
    ? rows.map((r) => Number(r[volKey]) || 0)
    : null;

  const series: SeriesOption[] = [
    {
      type: "candlestick",
      data: values,
      xAxisIndex: 0,
      yAxisIndex: 0,
      itemStyle: {
        color: "#0f766e",
        color0: "#b45309",
        borderColor: "#0f766e",
        borderColor0: "#b45309",
      },
    },
  ];

  if (volumes) {
    series.push({
      name: "Khối lượng",
      type: "bar",
      data: volumes,
      xAxisIndex: 1,
      yAxisIndex: 1,
      itemStyle: { color: "rgba(15,118,110,0.35)" },
    });
  }

  const dense = categories.length > CHART_DENSE_THRESHOLDS.dataZoom;
  const windowPct = dense
    ? Math.min(100, Math.max(12, Math.round(2400 / categories.length)))
    : 100;
  const dataZoom = dense
    ? [
        {
          type: "inside" as const,
          xAxisIndex: volumes ? [0, 1] : 0,
          start: 100 - windowPct,
          end: 100,
          zoomOnMouseWheel: true,
          moveOnMouseMove: true,
        },
        {
          type: "slider" as const,
          xAxisIndex: volumes ? [0, 1] : 0,
          start: 100 - windowPct,
          end: 100,
          bottom: 6,
          height: 18,
          brushSelect: false,
        },
      ]
    : undefined;

  return {
    animationDuration: 700,
    axisPointer: { link: [{ xAxisIndex: "all" }] },
    ...(dataZoom ? { dataZoom } : {}),
    grid: volumes
      ? [
          { left: 12, right: 16, top: 28, height: dense ? "48%" : "52%", containLabel: true },
          { left: 12, right: 16, top: dense ? "66%" : "68%", height: "22%", containLabel: true },
        ]
      : {
          left: 12,
          right: 16,
          top: 28,
          bottom: dense ? 64 : 40,
          containLabel: true,
        },
    tooltip: {
      trigger: "axis",
      backgroundColor: "rgba(255,255,255,0.96)",
      borderColor: "rgba(11,31,42,0.1)",
      borderWidth: 1,
      textStyle: { color: "#0b1f2a", fontSize: 12 },
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        const candle = list.find((p) => (p as { seriesType?: string }).seriesType === "candlestick") as
          | { axisValue?: string; value?: number[] }
          | undefined;
        const vol = list.find((p) => (p as { seriesName?: string }).seriesName === "Khối lượng") as
          | { value?: number }
          | undefined;
        const v = candle?.value || [];
        let html = `<b>${candle?.axisValue || ""}</b><br/>Mở: ${formatNumber(v[1], ohlc.open!)}<br/>Đóng: ${formatNumber(v[2], ohlc.close!)}<br/>Thấp: ${formatNumber(v[3], ohlc.low!)}<br/>Cao: ${formatNumber(v[4], ohlc.high!)}`;
        if (vol && volKey) {
          html += `<br/>KL: ${formatNumber(vol.value, volKey)}`;
        }
        return html;
      },
    },
    xAxis: volumes
      ? [
          {
            type: "category",
            data: categories,
            gridIndex: 0,
            axisLabel: { show: false },
            axisLine: { show: false },
            axisTick: { show: false },
          },
          {
            type: "category",
            data: categories,
            gridIndex: 1,
            axisLabel: { color: "#5b6b73", fontSize: 10 },
            axisLine: { show: false },
            axisTick: { show: false },
          },
        ]
      : {
          type: "category",
          data: categories,
          axisLabel: { color: "#5b6b73", fontSize: 11 },
          axisLine: { show: false },
          axisTick: { show: false },
        },
    yAxis: volumes
      ? [
          {
            type: "value",
            scale: true,
            gridIndex: 0,
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
          {
            type: "value",
            gridIndex: 1,
            axisLabel: {
              color: "#5b6b73",
              fontSize: 10,
              formatter: (v: number) => compactTick(v, volKey || "volume"),
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
    series,
  };
}

function buildRadarOption(
  data: Record<string, unknown>[],
  axes: RadarAxes,
  labels?: Record<string, string>,
): EChartsOption {
  const indicators = axes.metrics.map((m) => {
    const vals = data
      .map((r) => Math.abs(Number(r[m])))
      .filter((n) => Number.isFinite(n));
    const max = vals.length ? Math.max(...vals) * 1.15 : 1;
    return { name: friendlyLabel(m, labels), max: max || 1 };
  });

  const seriesData = data.slice(0, 8).map((row, i) => ({
    name: String(row[axes.entity] ?? i + 1),
    value: axes.metrics.map((m) => {
      const n = Number(row[m]);
      return Number.isFinite(n) ? n : 0;
    }),
    itemStyle: { color: COLORS[i % COLORS.length] },
    areaStyle: { opacity: 0.12 },
  }));

  return {
    animationDuration: 700,
    legend: {
      bottom: 0,
      textStyle: { color: "#5b6b73", fontSize: 11 },
    },
    tooltip: { trigger: "item" },
    radar: {
      indicator: indicators,
      center: ["50%", "48%"],
      radius: "62%",
      axisName: { color: "#5b6b73", fontSize: 11 },
      splitArea: {
        areaStyle: {
          color: ["rgba(15,118,110,0.03)", "rgba(15,118,110,0.07)"],
        },
      },
    },
    series: [
      {
        type: "radar",
        data: seriesData,
      },
    ],
  };
}

function buildWaterfallOption(
  data: Record<string, unknown>[],
  axes: WaterfallAxes,
  labels?: Record<string, string>,
): EChartsOption {
  const categories = data.map((r) => String(r[axes.category] ?? ""));
  const values = data.map((r) => {
    const n = Number(r[axes.value]);
    return Number.isFinite(n) ? n : 0;
  });

  // Tất cả ≥0 (xếp hạng/cơ cấu): mỗi cột là phần đóng góp chồng từ 0.
  // Có số âm: bridge waterfall (delta).
  const allNonNeg = values.every((v) => v >= 0);
  const helpers: number[] = [];
  const rises: (number | "-")[] = [];
  const falls: (number | "-")[] = [];
  if (allNonNeg) {
    let running = 0;
    for (const v of values) {
      helpers.push(running);
      rises.push(v);
      falls.push("-");
      running += v;
    }
  } else {
    let running = 0;
    for (let i = 0; i < values.length; i++) {
      const v = values[i];
      if (i === 0) {
        helpers.push(0);
        rises.push(v >= 0 ? v : "-");
        falls.push(v < 0 ? -v : "-");
        running = v;
        continue;
      }
      if (v >= 0) {
        helpers.push(running);
        rises.push(v);
        falls.push("-");
        running += v;
      } else {
        helpers.push(running + v);
        rises.push("-");
        falls.push(-v);
        running += v;
      }
    }
  }

  const waterfallZoom = buildCategoryDataZoom(categories.length, false, false);

  return {
    animationDuration: 700,
    ...(waterfallZoom ? { dataZoom: waterfallZoom } : {}),
    grid: {
      left: 12,
      right: 16,
      top: 28,
      bottom: categories.length > CHART_DENSE_THRESHOLDS.dataZoom ? 72 : 48,
      containLabel: true,
    },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (params) => {
        const list = Array.isArray(params) ? params : [params];
        const idx = (list[0] as { dataIndex?: number }).dataIndex ?? 0;
        return `<b>${categories[idx]}</b><br/>${friendlyLabel(axes.value, labels)}: ${formatNumber(values[idx], axes.value)}`;
      },
    },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: {
        color: "#5b6b73",
        fontSize: 11,
        rotate: categories.length > 6 ? 30 : 0,
        interval:
          categories.length > CHART_DENSE_THRESHOLDS.dataZoom
            ? ("auto" as const)
            : 0,
        hideOverlap: true,
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      axisLabel: {
        color: "#5b6b73",
        fontSize: 11,
        formatter: (v: number) => compactTick(v, axes.value),
      },
      splitLine: {
        lineStyle: { color: "rgba(11,31,42,0.07)", type: "dashed" },
      },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        name: "helper",
        type: "bar",
        stack: "wf",
        data: helpers,
        itemStyle: { borderColor: "transparent", color: "transparent" },
        emphasis: { itemStyle: { borderColor: "transparent", color: "transparent" } },
        tooltip: { show: false },
      },
      {
        name: "Tăng",
        type: "bar",
        stack: "wf",
        data: rises,
        itemStyle: { color: "#0f766e" },
      },
      {
        name: "Giảm",
        type: "bar",
        stack: "wf",
        data: falls,
        itemStyle: { color: "#b45309" },
      },
    ],
  };
}

function buildCategoryDataZoom(
  count: number,
  horizontal: boolean,
  isTimeSeries = false,
): EChartsOption["dataZoom"] | undefined {
  if (count <= CHART_DENSE_THRESHOLDS.dataZoom) return undefined;
  const windowPct = Math.min(100, Math.max(12, Math.round(2400 / count)));
  const start = isTimeSeries ? 100 - windowPct : 0;
  const end = isTimeSeries ? 100 : windowPct;

  if (horizontal) {
    return [
      {
        type: "inside",
        yAxisIndex: 0,
        start,
        end,
        zoomOnMouseWheel: true,
        moveOnMouseMove: true,
      },
      {
        type: "slider",
        yAxisIndex: 0,
        start,
        end,
        right: 4,
        width: 16,
        brushSelect: false,
      },
    ];
  }

  return [
    {
      type: "inside",
      xAxisIndex: 0,
      start,
      end,
      zoomOnMouseWheel: true,
      moveOnMouseMove: true,
    },
    {
      type: "slider",
      xAxisIndex: 0,
      start,
      end,
      bottom: 6,
      height: 18,
      brushSelect: false,
    },
  ];
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
  isTimeSeries = false,
}: {
  type: ChartType;
  chartData: Record<string, unknown>[];
  yCols: string[];
  labels?: Record<string, string>;
  horizontal: boolean;
  xLabel: string;
  forecast?: Forecast | null;
  showMovingAvg?: boolean;
  isTimeSeries?: boolean;
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
    const { rows: pieRows } = aggregatePieChartData(chartData, pieY);
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
        type: pieRows.length > 8 ? "scroll" : "plain",
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
            show: pieRows.length <= 10,
            formatter: "{b}\n{d}%",
            fontSize: 11,
            color: "#5b6b73",
          },
          data: pieRows.map((d, i) => ({
            name: String(d.name ?? ""),
            value: Number(d[pieY]) || 0,
            itemStyle: { color: COLORS[i % COLORS.length] },
          })),
        },
      ],
    };
  }

  const dense = categories.length > CHART_DENSE_THRESHOLDS.dataZoom;
  const dataZoom = buildCategoryDataZoom(categories.length, horizontal, isTimeSeries);

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
      ...(dataZoom ? { dataZoom } : {}),
      grid: {
        ...baseGrid,
        right: dense ? 36 : baseGrid.right,
      },
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
        axisLabel: {
          ...axisLabel,
          interval: dense ? ("auto" as const) : 0,
          hideOverlap: true,
        },
        axisLine: { show: false },
        axisTick: { show: false },
      },
      series,
    };
  }

  return {
    color: COLORS,
    animationDuration: 700,
    ...(dataZoom ? { dataZoom } : {}),
    grid: {
      ...baseGrid,
      bottom: dense ? 72 : baseGrid.bottom,
    },
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
        interval: dense ? ("auto" as const) : 0,
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
