import type { ChartType } from "./types";

const VIZ_ONLY =
  /(làm|lam|vẽ|ve|đổi|doi|chuyển|chuyen|cho\s+tôi|cho\s+toi|tạo|tao|hiển\s*thị|hien\s*thi|xem).{0,60}(biểu\s*đồ|bieu\s*do|chart|tròn|tron|cột|cot|đường|duong|miền|mien|vùng|vung|pie|bar|line|area|combo)/i;

const DATA_ASK =
  /(liệt\s*kê|liet\s*ke|tổng|tong|trung\s*bình|trung\s*binh|theo\s*từng|dự\s*án|du\s*an|mỏ|trữ\s*lượng|phân\s*tích|so\s*sánh|bao\s*nhiêu|top|diễn\s*biến|dien\s*bien)/i;

const CHART_PATTERNS: [ChartType, RegExp][] = [
  ["candlestick", /(biểu\s*đồ|bieu\s*do).{0,30}(nến|nen|candle)|candlestick|ohlc/i],
  ["area", /(biểu\s*đồ|bieu\s*do).{0,30}(miền|mien|vùng|vung|area)|area\s*chart/i],
  ["line", /(biểu\s*đồ|bieu\s*do).{0,30}(đường|duong|line)|line\s*chart|xu\s*hướng|theo\s*(thời\s*gian|ngày)/i],
  ["combo", /(combo|kết\s*hợp|giá\s*và\s*khối\s*lượng|price\s*and\s*volume)/i],
  ["bar", /(biểu\s*đồ|bieu\s*do).{0,30}(cột|cot|bar)|bar\s*chart/i],
  ["pie", /(biểu\s*đồ|bieu\s*do).{0,30}(tròn|tron|pie)|pie\s*chart|cơ\s*cấu|tỷ\s*trọng/i],
  ["table", /(chỉ\s*(hiển\s*thị\s*)?bảng|table\s*only|không\s*(cần\s*)?biểu\s*đồ)/i],
];

const ENTITY_COL =
  /^(ticker|symbol|ma_cp|ma\s*cp|company_name|short_name|project_name|area_name|owner|department|province|mineral_type|status)$/i;

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

  const { yCols } = pickChartAxes(data);

  if (requested === "combo" && yCols.length < 2) return "bar";

  if (requested === "pie") {
    if (data.length > 12) return "bar";
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
  if (requested === "combo" && refined === "bar")
    return "Combo cần ≥2 cột số — đã chuyển sang cột.";
  if (requested === "candlestick" && refined !== "candlestick")
    return "Thiếu cột OHLC — đã chuyển sang đường.";
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
