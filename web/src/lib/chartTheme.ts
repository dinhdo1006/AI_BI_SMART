/**
 * Theme biểu đồ báo cáo — rõ, chi tiết, dễ đọc.
 * Đồng bộ với design system: teal / copper / ink / foam.
 */

import type { EChartsOption } from "echarts";
import { formatNumber, friendlyLabel } from "./format";

/** Pallete phân biệt tốt trên nền trắng (tối đa ~8 series). */
export const CHART_COLORS = [
  "#0f766e", // teal
  "#b45309", // copper
  "#1e3a5f", // navy
  "#0e7490", // cyan
  "#a16207", // amber
  "#047857", // emerald
  "#7c3aed", // violet (secondary contrast)
  "#57534e", // stone
] as const;

export const CHART_INK = "#0b1f2a";
export const CHART_MUTED = "#5b6b73";
export const CHART_LINE = "rgba(11,31,42,0.08)";
export const CHART_LINE_STRONG = "rgba(11,31,42,0.14)";

export const axisLabelStyle = {
  color: CHART_MUTED,
  fontSize: 11,
  fontFamily: "ui-sans-serif, system-ui, sans-serif",
} as const;

export const nameTextStyle = {
  color: CHART_MUTED,
  fontSize: 11,
  fontWeight: 600 as const,
};

/** Grid chuẩn báo cáo — chừa chỗ legend + dataZoom. */
export function reportGrid(opts?: {
  horizontal?: boolean;
  dense?: boolean;
  dualY?: boolean;
  hasLegend?: boolean;
}): EChartsOption["grid"] {
  const dense = opts?.dense;
  const hasLegend = opts?.hasLegend !== false;
  if (opts?.horizontal) {
    return {
      left: 96,
      right: dense ? 40 : 28,
      top: hasLegend ? 40 : 24,
      bottom: 28,
      containLabel: false,
    };
  }
  return {
    left: 12,
    right: opts?.dualY ? 56 : 20,
    top: hasLegend ? 44 : 28,
    bottom: dense ? 72 : 52,
    containLabel: true,
  };
}

export function reportLegend(
  labels?: Record<string, string> | null,
  opts?: { many?: boolean },
): EChartsOption["legend"] {
  return {
    top: 4,
    type: opts?.many ? "scroll" : "plain",
    left: "center",
    itemWidth: 12,
    itemHeight: 8,
    itemGap: 14,
    textStyle: {
      color: CHART_MUTED,
      fontSize: 11,
      fontWeight: 500,
    },
    pageIconColor: CHART_MUTED,
    pageTextStyle: { color: CHART_MUTED, fontSize: 10 },
    formatter: (name: string) => friendlyLabel(name, labels),
  };
}

export function reportTooltipBase(): NonNullable<EChartsOption["tooltip"]> {
  return {
    backgroundColor: "rgba(255,255,255,0.98)",
    borderColor: "rgba(11,31,42,0.12)",
    borderWidth: 1,
    padding: [10, 12],
    extraCssText:
      "box-shadow:0 8px 24px rgba(11,31,42,0.12);border-radius:10px;",
    textStyle: {
      color: CHART_INK,
      fontSize: 12,
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
    },
  };
}

/** Tooltip trục (line/bar) — bảng giá trị rõ ràng. */
export function reportAxisTooltip(
  labels?: Record<string, string> | null,
  valueFormatCol?: string,
  opts?: { crosshair?: boolean },
): EChartsOption["tooltip"] {
  return {
    ...reportTooltipBase(),
    trigger: "axis",
    axisPointer: opts?.crosshair
      ? {
          type: "cross",
          crossStyle: { color: "rgba(15,118,110,0.35)" },
          lineStyle: { color: "rgba(15,118,110,0.35)", type: "dashed" },
          label: {
            backgroundColor: "#0f766e",
            color: "#fff",
            fontSize: 10,
            borderRadius: 4,
            padding: [2, 6],
          },
        }
      : {
          type: "shadow",
          shadowStyle: { color: "rgba(15,118,110,0.08)" },
        },
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
            value?: number | null | number[];
          };
          const key = item.seriesName || "";
          const fmtCol = valueFormatCol || key;
          let raw: unknown = item.value;
          if (Array.isArray(raw)) raw = raw[raw.length - 1];
          return (
            `<tr>` +
            `<td style="padding:2px 10px 2px 0;white-space:nowrap">${item.marker || ""} ${friendlyLabel(key, labels)}</td>` +
            `<td style="padding:2px 0;text-align:right;font-weight:700;font-variant-numeric:tabular-nums">${formatNumber(raw, fmtCol)}</td>` +
            `</tr>`
          );
        })
        .join("");
      return (
        `<div style="margin-bottom:6px;font-weight:700;font-size:12px;color:${CHART_INK}">${title}</div>` +
        `<table style="border-collapse:collapse;font-size:12px;color:${CHART_MUTED}">${rows}</table>`
      );
    },
  };
}

export function reportSplitLine() {
  return {
    show: true,
    lineStyle: { color: CHART_LINE, type: "dashed" as const, width: 1 },
  };
}

export function reportValueAxis(
  colHint: string,
  opts?: { max?: number; scale?: boolean },
): Record<string, unknown> {
  return {
    type: "value",
    max: opts?.max,
    scale: opts?.scale ?? opts?.max == null,
    axisLabel: {
      ...axisLabelStyle,
      formatter: (v: number) => compactTick(v, colHint),
    },
    splitLine: reportSplitLine(),
    axisLine: { show: false },
    axisTick: { show: false },
  };
}

export function reportCategoryAxis(
  categories: string[],
  opts?: {
    name?: string;
    dense?: boolean;
    rotate?: number;
  },
): Record<string, unknown> {
  const dense = opts?.dense ?? categories.length > CHART_DENSE_LABEL;
  return {
    type: "category",
    data: categories,
    name: opts?.name,
    nameLocation: "middle",
    nameGap: 32,
    nameTextStyle: {
      ...nameTextStyle,
      opacity: opts?.name ? 0.85 : 0,
    },
    axisLabel: {
      ...axisLabelStyle,
      rotate: opts?.rotate ?? (categories.length > 8 ? 28 : 0),
      interval: dense ? ("auto" as const) : 0,
      hideOverlap: true,
      margin: 10,
    },
    axisLine: { show: false },
    axisTick: { show: false },
    splitLine: { show: false },
  };
}

const CHART_DENSE_LABEL = 24;

export function compactTick(v: number, colHint: string): string {
  if (!Number.isFinite(v)) return "";
  if (Math.abs(v) >= 1_000_000_000)
    return `${(v / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tỷ`;
  if (Math.abs(v) >= 1_000_000)
    return `${(v / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 1 })} tr`;
  if (Math.abs(v) >= 10_000)
    return v.toLocaleString("vi-VN", { maximumFractionDigits: 0 });
  if (/roe|roa|pct|percent/i.test(colHint)) {
    return v.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
  }
  return v.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
}

export function hexAlpha(hex: string, alpha: number): string {
  const h = hex.replace("#", "");
  const r = parseInt(h.slice(0, 2), 16);
  const g = parseInt(h.slice(2, 4), 16);
  const b = parseInt(h.slice(4, 6), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

export function shade(hex: string, percent: number): string {
  const h = hex.replace("#", "");
  const num = parseInt(h, 16);
  const amt = Math.round(2.55 * percent);
  const r = Math.min(255, Math.max(0, (num >> 16) + amt));
  const g = Math.min(255, Math.max(0, ((num >> 8) & 0xff) + amt));
  const b = Math.min(255, Math.max(0, (num & 0xff) + amt));
  return `#${((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1)}`;
}

/** Chiều cao tối thiểu theo loại — dễ nhìn hơn. */
export const CHART_HEIGHTS = {
  default: 340,
  withZoom: 400,
  candlestick: 440,
  radar: 400,
  treemap: 400,
  heatmapMin: 300,
} as const;

/** Merge theme mặc định vào mọi option. */
export function withReportTheme(option: EChartsOption): EChartsOption {
  return {
    animationDuration: 650,
    animationEasing: "cubicOut",
    textStyle: {
      fontFamily: "ui-sans-serif, system-ui, sans-serif",
      color: CHART_INK,
    },
    ...option,
    color: option.color ?? [...CHART_COLORS],
  };
}
