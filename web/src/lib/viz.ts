import type { ChartType } from "./types";

const VIZ_ONLY =
  /(làm|lam|vẽ|ve|đổi|doi|chuyển|chuyen|cho\s+tôi|cho\s+toi|tạo|tao|hiển\s*thị|hien\s*thi|xem).{0,60}(biểu\s*đồ|bieu\s*do|chart|tròn|tron|cột|cot|đường|duong|miền|mien|vùng|vung|pie|bar|line|area|combo)/i;

const DATA_ASK =
  /(liệt\s*kê|liet\s*ke|tổng|tong|trung\s*bình|trung\s*binh|theo\s*từng|dự\s*án|du\s*an|mỏ|trữ\s*lượng|phân\s*tích|so\s*sánh|bao\s*nhiêu|top|diễn\s*biến|dien\s*bien)/i;

const CHART_PATTERNS: [ChartType, RegExp][] = [
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

  const yCols = preferred.slice(0, 4);
  const isTimeSeries = Boolean(dateLike[0] && x === dateLike[0]);
  const isComparison =
    Boolean(entity && x === entity) && uniqueCount(data, entity!) <= 20;

  return { x, yCols, dateLike, isTimeSeries, isComparison, entity };
}

function metricScore(col: string): number {
  const c = col.toLowerCase();
  if (/pe_ratio|^pe$|pb_ratio|^pb$|eps|roe|roa|market_cap|von_hoa/.test(c))
    return 50;
  if (PRICE_COL.test(c)) return 40;
  if (VOLUME_COL.test(c)) return 35;
  if (/revenue|income|profit|budget|tonnage|completion/.test(c)) return 30;
  if (/id$|year|quarter/.test(c)) return -10;
  return 10;
}

/** Điều chỉnh loại chart cho hợp dữ liệu (so sánh mã → cột nhóm, giá+KL → combo). */
export function refineChartType(
  requested: ChartType,
  data: Record<string, unknown>[],
): ChartType {
  if (requested === "table" || requested === "pie") return requested;
  const axes = pickChartAxes(data);
  if (!axes.yCols.length) return "table";

  const hasPrice = axes.yCols.some((c) => PRICE_COL.test(c));
  const hasVol = axes.yCols.some((c) => VOLUME_COL.test(c));

  if (axes.isTimeSeries && hasPrice && hasVol) return "combo";
  if (axes.isTimeSeries && requested === "bar") return "line";
  if (axes.isComparison) {
    // So sánh FPT/HPG/VCB: cột nhóm đẹp hơn combo lệch scale
    if (requested === "combo" || requested === "line" || requested === "area") {
      return "bar";
    }
  }
  return requested;
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
