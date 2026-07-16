import type { ChartType } from "./types";

const VIZ_ONLY =
  /(làm|lam|vẽ|ve|đổi|doi|chuyển|chuyen|cho\s+tôi|cho\s+toi|tạo|tao|hiển\s*thị|hien\s*thi|xem).{0,60}(biểu\s*đồ|bieu\s*do|chart|tròn|tron|cột|cot|đường|duong|miền|mien|vùng|vung|pie|bar|line|area|combo|heatmap|scatter|treemap|radar|waterfall|nhiệt|phan\s*tán|phân\s*tán|cây)/i;

const DATA_ASK =
  /(liệt\s*kê|liet\s*ke|tổng|tong|trung\s*bình|trung\s*binh|theo\s*từng|dự\s*án|du\s*an|mỏ|trữ\s*lượng|phân\s*tích|so\s*sánh|bao\s*nhiêu|top|diễn\s*biến|dien\s*bien)/i;

const CHART_PATTERNS: [ChartType, RegExp][] = [
  ["candlestick", /(biểu\s*đồ|bieu\s*do).{0,30}(nến|nen|candle)|candlestick|ohlc/i],
  [
    "waterfall",
    /(biểu\s*đồ|bieu\s*do).{0,30}(thác|thac|waterfall)|waterfall|đóng\s*góp|dong\s*gop/i,
  ],
  [
    "radar",
    /(biểu\s*đồ|bieu\s*do).{0,30}(radar|mạng\s*nhện|mang\s*nhen|spider)|radar\s*chart|spider\s*chart/i,
  ],
  [
    "heatmap",
    /(biểu\s*đồ|bieu\s*do).{0,30}(nhiệt|nhiet|heatmap)|heatmap|ma\s*trận|ma\s*tran|heat\s*map/i,
  ],
  [
    "scatter",
    /(biểu\s*đồ|bieu\s*do).{0,30}(phân\s*tán|phan\s*tan|scatter)|scatter|tương\s*quan|tuong\s*quan|xy\s*plot/i,
  ],
  [
    "treemap",
    /(biểu\s*đồ|bieu\s*do).{0,30}(cây|cay|treemap|khối|khoi)|treemap|tree\s*map|ô\s*vuông|o\s*vuong/i,
  ],
  ["area", /(biểu\s*đồ|bieu\s*do).{0,30}(miền|mien|vùng|vung|area)|area\s*chart/i],
  ["line", /(biểu\s*đồ|bieu\s*do).{0,30}(đường|duong|line)|line\s*chart|xu\s*hướng|theo\s*(thời\s*gian|ngày)|dự\s*báo|du\s*bao|forecast/i],
  ["combo", /(combo|kết\s*hợp|giá\s*và\s*khối\s*lượng|price\s*and\s*volume)/i],
  ["bar", /(biểu\s*đồ|bieu\s*do).{0,30}(cột|cot|bar)|bar\s*chart/i],
  ["pie", /(biểu\s*đồ|bieu\s*do).{0,30}(tròn|tron|pie)|pie\s*chart|cơ\s*cấu|tỷ\s*trọng/i],
  ["table", /(chỉ\s*(hiển\s*thị\s*)?bảng|table\s*only|không\s*(cần\s*)?biểu\s*đồ)/i],
];

const ENTITY_COL =
  /^(ticker|symbol|ma_cp|ma\s*cp|company_name|short_name|project_name|area_name|owner|department|province|mineral_type|status|sector|industry)$/i;

const PRICE_COL = /(close_price|open_price|high_price|low_price|adjusted_price|gia|price)/i;
const VOLUME_COL = /(volume|khoi_luong|khối lượng|value|gia_tri)/i;

export function isVizOnlyRequest(query: string): boolean {
  const q = query.trim();
  if (q.length > 120) return false;
  const hasData = DATA_ASK.test(q);
  const chart = detectChartFromText(q);
  if (chart && !hasData) return true;
  return VIZ_ONLY.test(q) && !hasData;
}

export function detectChartFromText(text: string): ChartType | null {
  for (const [chart, re] of CHART_PATTERNS) {
    if (re.test(text)) return chart;
  }
  return null;
}

export function chartQueryForType(chart: ChartType): string {
  const map: Record<ChartType, string> = {
    bar: "Vẽ biểu đồ cột",
    line: "Vẽ biểu đồ đường",
    area: "Vẽ biểu đồ miền",
    pie: "Vẽ biểu đồ tròn",
    combo: "Vẽ biểu đồ combo",
    candlestick: "Vẽ biểu đồ nến",
    heatmap: "Vẽ biểu đồ nhiệt",
    scatter: "Vẽ biểu đồ phân tán",
    treemap: "Vẽ biểu đồ cây",
    radar: "Vẽ biểu đồ radar",
    waterfall: "Vẽ biểu đồ thác nước",
    table: "Chỉ hiển thị bảng",
  };
  return map[chart];
}

function isNumeric(v: unknown): boolean {
  return typeof v === "number" && Number.isFinite(v);
}

function uniqueCount(data: Record<string, unknown>[], col: string): number {
  return new Set(data.map((r) => String(r[col] ?? ""))).size;
}

export function analyzeColumns(data: Record<string, unknown>[]) {
  if (!data.length) {
    return {
      numeric: [] as string[],
      categorical: [] as string[],
      dateLike: [] as string[],
    };
  }
  const cols = Object.keys(data[0]);
  const sample = data.slice(0, 30);
  const numeric: string[] = [];
  const categorical: string[] = [];
  const dateLike: string[] = [];

  for (const c of cols) {
    const values = sample.map((r) => r[c]).filter((v) => v != null);
    if (!values.length) {
      categorical.push(c);
      continue;
    }
    const lower = c.toLowerCase();
    if (
      lower.includes("date") ||
      lower.includes("ngay") ||
      /trade_date|calc_date|updated_at|surveyed_at|start_date/.test(lower)
    ) {
      dateLike.push(c);
      continue;
    }
    const nums = values.filter(isNumeric);
    if (nums.length >= values.length * 0.7) numeric.push(c);
    else categorical.push(c);
  }
  return { numeric, categorical, dateLike };
}

export function pickChartAxes(data: Record<string, unknown>[]) {
  const { numeric, categorical, dateLike } = analyzeColumns(data);
  const entity =
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c));

  let x: string | undefined;

  // So sánh nhiều mã / danh mục: ưu tiên entity, không dùng ngày trùng
  if (entity && uniqueCount(data, entity) >= 2) {
    const dateCol = dateLike[0];
    if (!dateCol || uniqueCount(data, dateCol) <= uniqueCount(data, entity)) {
      x = entity;
    }
  }

  // Chuỗi thời gian: ưu tiên ngày
  if (!x && dateLike[0] && uniqueCount(data, dateLike[0]) >= 3) {
    x = dateLike[0];
  }

  if (!x) {
    x =
      entity ||
      dateLike[0] ||
      categorical.find((c) => !/id$/i.test(c)) ||
      categorical[0] ||
      Object.keys(data[0] || {})[0];
  }

  // Ưu tiên metric “ý nghĩa” trước (P/E, giá, vốn hóa…) thay vì calc_date số
  const preferred = numeric
    .filter((c) => c !== x)
    .sort((a, b) => metricScore(b) - metricScore(a));

  // Cùng thang đo — tránh EPS (nghìn) che P/E·P/B·ROE (đơn vị)
  const yCols = selectCompatibleYCols(data, preferred).slice(0, 4);
  const isTimeSeries = Boolean(dateLike[0] && x === dateLike[0]);
  const isComparison =
    Boolean(entity && x === entity) && uniqueCount(data, entity!) <= 20;

  return { x, yCols, dateLike, isTimeSeries, isComparison, entity };
}

function colMedianAbs(data: Record<string, unknown>[], col: string): number {
  const vals = data
    .map((r) => Math.abs(Number(r[col])))
    .filter((n) => Number.isFinite(n) && n > 0)
    .sort((a, b) => a - b);
  if (!vals.length) return 0;
  return vals[Math.floor(vals.length / 2)];
}

/** Giữ các cột cùng bậc độ lớn (tỷ lệ max/min median ≤ 80). */
export function selectCompatibleYCols(
  data: Record<string, unknown>[],
  preferred: string[],
): string[] {
  if (preferred.length <= 1) return preferred;

  const ratioCols = preferred.filter((c) =>
    /pe_ratio|^pe$|pb_ratio|^pb$|roe|roa|de_ratio|change_percent|completion_pct/i.test(
      c,
    ),
  );
  // So sánh định giá: ưu tiên nhóm tỷ lệ (bỏ EPS/vốn hóa lệch scale)
  if (ratioCols.length >= 2) return ratioCols;

  const withMed = preferred
    .map((c) => ({ c, m: colMedianAbs(data, c) }))
    .filter((x) => x.m > 0);
  if (!withMed.length) return preferred.slice(0, 3);

  const anchor = withMed[0].m;
  const compatible = withMed
    .filter((x) => {
      const ratio = Math.max(x.m, anchor) / Math.min(x.m, anchor);
      return ratio <= 80;
    })
    .map((x) => x.c);

  return compatible.length ? compatible : preferred.slice(0, 2);
}

export function metricScore(col: string): number {
  const c = col.toLowerCase();
  if (/pe_ratio|^pe$|pb_ratio|^pb$|roe|roa/.test(c)) return 60;
  if (/eps|market_cap|von_hoa/.test(c)) return 45;
  if (PRICE_COL.test(c)) return 40;
  if (VOLUME_COL.test(c)) return 35;
  if (/revenue|income|profit|budget|tonnage|completion/.test(c)) return 30;
  if (/id$|year|quarter/.test(c)) return -10;
  return 10;
}

/** Nhận diện cột OHLC cho biểu đồ nến. */
export function detectOhlcColumns(data: Record<string, unknown>[]): {
  open?: string;
  high?: string;
  low?: string;
  close?: string;
  date?: string;
} | null {
  if (!data.length) return null;
  const cols = Object.keys(data[0]);
  const find = (re: RegExp) => cols.find((c) => re.test(c));
  const open = find(/^open(_price)?$|gia_mo|open_price/i);
  const high = find(/^high(_price)?$|gia_cao|high_price/i);
  const low = find(/^low(_price)?$|gia_thap|low_price/i);
  const close = find(/^close(_price)?$|gia_dong|adjusted_price|close_price/i);
  const date = find(/date|ngay|trade_date|calc_date/i);
  if (open && high && low && close) return { open, high, low, close, date };
  return null;
}

export type HeatmapAxes =
  | {
      mode: "pivot";
      row: string;
      col: string;
      value: string;
    }
  | {
      mode: "metrics";
      row: string;
      metrics: string[];
    };

/** Trục heatmap: 2 danh mục + 1 số, hoặc 1 danh mục × nhiều metric. */
export function pickHeatmapAxes(
  data: Record<string, unknown>[],
): HeatmapAxes | null {
  if (!data.length) return null;
  const { numeric, categorical, dateLike } = analyzeColumns(data);
  const entity =
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c));
  const preferred = [...numeric].sort(
    (a, b) => metricScore(b) - metricScore(a),
  );

  if (entity && dateLike[0] && preferred[0]) {
    if (uniqueCount(data, entity) >= 2 && uniqueCount(data, dateLike[0]) >= 2) {
      return {
        mode: "pivot",
        row: entity,
        col: dateLike[0],
        value: preferred[0],
      };
    }
  }

  if (categorical.length >= 2 && preferred[0]) {
    const row = entity || categorical[0];
    // Prefer a non-entity column as col axis to avoid sparse diagonal pivots
    // (e.g. ticker × company_name both match ENTITY_COL but map 1:1)
    const col =
      categorical.find((c) => c !== row && !ENTITY_COL.test(c)) ??
      categorical.find((c) => c !== row);
    if (
      col &&
      !(ENTITY_COL.test(row) && ENTITY_COL.test(col)) &&
      uniqueCount(data, row) >= 2 &&
      uniqueCount(data, col) >= 2
    ) {
      return { mode: "pivot", row, col, value: preferred[0] };
    }
  }

  if (entity && preferred.length >= 2) {
    return {
      mode: "metrics",
      row: entity,
      metrics: preferred.slice(0, 8),
    };
  }

  return null;
}

/** Cột phụ để phân biệt khi cùng mã xuất hiện nhiều dòng (ngày, kỳ, …). */
export function detectHeatmapDisambiguator(
  data: Record<string, unknown>[],
  entityKey: string,
  metricKeys: string[],
): string | null {
  if (!data.length) return null;
  const entityVals = data.map((r) => String(r[entityKey] ?? ""));
  if (new Set(entityVals).size >= data.length) return null;

  const cols = Object.keys(data[0]);
  const dateCol = cols.find((c) =>
    /date|ngay|trade_date|calc_date|period|fiscal|quarter|year/i.test(c),
  );
  if (dateCol) return dateCol;

  return (
    cols.find(
      (c) =>
        c !== entityKey &&
        !metricKeys.includes(c) &&
        !/id$/i.test(c) &&
        !ENTITY_COL.test(c),
    ) ?? null
  );
}

/** Nhãn hàng heatmap: mã + ngày/kỳ khi trùng mã. */
export function buildHeatmapRowLabel(
  row: Record<string, unknown>,
  entityKey: string,
  disambiguator?: string | null,
): string {
  const entity = String(row[entityKey] ?? "");
  if (!disambiguator) return entity;
  const extra = formatHeatmapAxisLabel(row[disambiguator], disambiguator);
  return extra ? `${entity} · ${extra}` : entity;
}

function formatHeatmapAxisLabel(value: unknown, col: string): string {
  if (value == null) return "";
  const s = String(value);
  if (/date|ngay/i.test(col) && /^\d{4}-\d{2}-\d{2}/.test(s)) {
    return s.slice(0, 10);
  }
  return s.length > 14 ? `${s.slice(0, 12)}…` : s;
}

export type ScatterAxes = {
  x: string;
  y: string;
  size?: string;
  label?: string;
};

/** Hai cột số độc lập cho scatter (+ nhãn entity nếu có). */
export function pickScatterAxes(
  data: Record<string, unknown>[],
): ScatterAxes | null {
  if (!data.length) return null;
  const { numeric, categorical } = analyzeColumns(data);
  const preferred = [...numeric].sort(
    (a, b) => metricScore(b) - metricScore(a),
  );
  if (preferred.length < 2) return null;
  const entity =
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c));
  return {
    x: preferred[0],
    y: preferred[1],
    size: preferred[2],
    label: entity,
  };
}

export type TreemapAxes = {
  name: string;
  value: string;
};

export function pickTreemapAxes(
  data: Record<string, unknown>[],
): TreemapAxes | null {
  if (!data.length) return null;
  const { numeric, categorical } = analyzeColumns(data);
  const name =
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c)) ||
    categorical[0];
  const preferred = [...numeric].sort(
    (a, b) => metricScore(b) - metricScore(a),
  );
  if (!name || !preferred[0]) return null;
  return { name, value: preferred[0] };
}

export type RadarAxes = {
  entity: string;
  metrics: string[];
};

export function pickRadarAxes(
  data: Record<string, unknown>[],
): RadarAxes | null {
  if (!data.length) return null;
  const { numeric, categorical } = analyzeColumns(data);
  const entity =
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c));
  const metrics = [...numeric]
    .sort((a, b) => metricScore(b) - metricScore(a))
    .slice(0, 8);
  if (!entity || metrics.length < 3) return null;
  if (uniqueCount(data, entity) < 2 || data.length > 12) return null;
  return { entity, metrics };
}

export type WaterfallAxes = {
  category: string;
  value: string;
};

export function pickWaterfallAxes(
  data: Record<string, unknown>[],
): WaterfallAxes | null {
  if (!data.length) return null;
  const { numeric, categorical, dateLike } = analyzeColumns(data);
  if (dateLike.length && uniqueCount(data, dateLike[0]) >= 3) return null;
  const category =
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c)) ||
    categorical[0];
  const preferred = [...numeric].sort(
    (a, b) => metricScore(b) - metricScore(a),
  );
  if (!category || !preferred[0]) return null;
  if (data.length < 3 || data.length > 20) return null;
  return { category, value: preferred[0] };
}

/** Các loại chart render được với data hiện tại. */
export function compatibleCharts(
  data: Record<string, unknown>[],
): ChartType[] {
  if (!data.length) return ["table"];
  const { numeric, categorical, dateLike } = analyzeColumns(data);
  const out: ChartType[] = ["table"];
  if (!numeric.length) return out;

  out.push("bar");
  if (dateLike.length) out.push("line", "area");
  if (numeric.length >= 2 && dateLike.length) out.push("combo");
  if (detectOhlcColumns(data)) out.push("candlestick");
  if (pickHeatmapAxes(data)) out.push("heatmap");
  if (pickScatterAxes(data)) out.push("scatter");
  if (categorical.length && numeric.length && data.length >= 2) {
    if (data.length <= 12) out.push("pie");
    out.push("treemap");
  }
  if (pickRadarAxes(data)) out.push("radar");
  if (pickWaterfallAxes(data)) out.push("waterfall");

  return [...new Set(out)];
}

/**
 * Điều chỉnh loại chart khi dữ liệu không phù hợp.
 */
export function refineChartType(
  requested: ChartType,
  data: Record<string, unknown>[],
): ChartType {
  if (requested === "table") return "table";

  if (requested === "candlestick") {
    return detectOhlcColumns(data) ? "candlestick" : "line";
  }

  if (requested === "heatmap") {
    return pickHeatmapAxes(data) ? "heatmap" : "bar";
  }

  if (requested === "scatter") {
    return pickScatterAxes(data) ? "scatter" : "bar";
  }

  if (requested === "treemap") {
    return pickTreemapAxes(data) ? "treemap" : "pie";
  }

  if (requested === "radar") {
    return pickRadarAxes(data) ? "radar" : "bar";
  }

  if (requested === "waterfall") {
    return pickWaterfallAxes(data) ? "waterfall" : "bar";
  }

  const { yCols } = pickChartAxes(data);

  if (requested === "combo" && yCols.length < 2) return "bar";

  if (requested === "pie") {
    if (data.length > 12) return pickTreemapAxes(data) ? "treemap" : "bar";
    if (yCols.length === 0) return "table";
  }

  return requested;
}

export function chartTypeHint(
  requested: ChartType,
  data: Record<string, unknown>[],
): string | null {
  const refined = refineChartType(requested, data);
  if (refined === requested) return null;
  if (requested === "pie" && refined === "bar")
    return "Pie không phù hợp khi >12 dòng — đã chuyển sang cột.";
  if (requested === "pie" && refined === "treemap")
    return "Nhiều danh mục — đã chuyển sang treemap (cây).";
  if (requested === "combo" && refined === "bar")
    return "Combo cần ≥2 cột số — đã chuyển sang cột.";
  if (requested === "candlestick" && refined !== "candlestick")
    return "Thiếu cột OHLC — đã chuyển sang đường.";
  if (requested === "heatmap" && refined !== "heatmap")
    return "Thiếu ma trận phù hợp — đã chuyển sang cột.";
  if (requested === "scatter" && refined !== "scatter")
    return "Cần ≥2 cột số — đã chuyển sang cột.";
  if (requested === "treemap" && refined !== "treemap")
    return "Thiếu danh mục/giá trị — đã chuyển sang tròn.";
  if (requested === "radar" && refined !== "radar")
    return "Radar cần ≥3 chỉ số và vài mã — đã chuyển sang cột.";
  if (requested === "waterfall" && refined !== "waterfall")
    return "Waterfall cần danh mục + 1 metric — đã chuyển sang cột.";
  return `Đã điều chỉnh sang ${refined}.`;
}

export function shouldUseHorizontalBar(
  data: Record<string, unknown>[],
  xCol: string,
): boolean {
  if (data.length > 8) return true;
  const labels = data.map((r) => String(r[xCol] ?? ""));
  const avgLen =
    labels.reduce((s, t) => s + t.length, 0) / Math.max(labels.length, 1);
  return avgLen > 12 || data.length > 6;
}

/** Moving average đơn giản; null ở đầu chuỗi cho đến khi đủ cửa sổ. */
export function movingAverage(
  values: (number | null)[],
  window: number,
): (number | null)[] {
  if (window < 2) return values;
  const out: (number | null)[] = [];
  for (let i = 0; i < values.length; i++) {
    if (i + 1 < window) {
      out.push(null);
      continue;
    }
    let sum = 0;
    let count = 0;
    for (let j = i - window + 1; j <= i; j++) {
      const v = values[j];
      if (v != null && Number.isFinite(v)) {
        sum += v;
        count += 1;
      }
    }
    out.push(count === window ? sum / window : null);
  }
  return out;
}

/** Ngưỡng hiển thị khi dữ liệu quá dày. */
export const CHART_DENSE_THRESHOLDS = {
  dataZoom: 24,
  pieMaxSlices: 12,
  heatmapMaxDim: 80,
  heatmapZoomDim: 16,
  scatterLarge: 120,
  horizontalBarRowHeight: 28,
  horizontalBarMinHeight: 310,
  horizontalBarMaxHeight: 720,
} as const;

export type ChartDensityInfo = {
  totalPoints: number;
  displayedPoints: number;
  truncated: boolean;
  needsZoom: boolean;
  message?: string;
};

/** Thông báo gợi ý khi biểu đồ có quá nhiều điểm. */
export function buildChartDensityInfo(
  totalPoints: number,
  displayedPoints: number,
  opts?: {
    needsZoom?: boolean;
    truncated?: boolean;
    extra?: string;
  },
): ChartDensityInfo | null {
  const truncated = opts?.truncated ?? displayedPoints < totalPoints;
  const needsZoom = opts?.needsZoom ?? false;
  if (!truncated && !needsZoom) return null;

  const parts: string[] = [];
  if (truncated) {
    parts.push(
      `Hiển thị ${displayedPoints.toLocaleString("vi-VN")}/${totalPoints.toLocaleString("vi-VN")} điểm`,
    );
  }
  if (needsZoom) {
    parts.push(
      `${totalPoints.toLocaleString("vi-VN")} điểm — kéo thanh zoom hoặc cuộn chuột để xem toàn bộ`,
    );
  }
  if (opts?.extra) parts.push(opts.extra);

  return {
    totalPoints,
    displayedPoints,
    truncated,
    needsZoom,
    message: parts.join(" · "),
  };
}

/** Gom các lát pie nhỏ thành "Khác" khi quá nhiều danh mục. */
export function aggregatePieChartData(
  rows: Record<string, unknown>[],
  valueKey: string,
  maxSlices = CHART_DENSE_THRESHOLDS.pieMaxSlices,
): {
  rows: Record<string, unknown>[];
  aggregated: boolean;
  hiddenCount: number;
} {
  if (rows.length <= maxSlices) {
    return { rows, aggregated: false, hiddenCount: 0 };
  }
  const sorted = [...rows].sort(
    (a, b) => (Number(b[valueKey]) || 0) - (Number(a[valueKey]) || 0),
  );
  const top = sorted.slice(0, maxSlices - 1);
  const rest = sorted.slice(maxSlices - 1);
  const otherSum = rest.reduce((s, r) => s + (Number(r[valueKey]) || 0), 0);
  return {
    rows: [
      ...top,
      { name: `Khác (${rest.length})`, [valueKey]: otherSum },
    ],
    aggregated: true,
    hiddenCount: rest.length,
  };
}
