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

export function analyzeColumns(data: Record<string, unknown>[]) {
  if (!data.length) return { numeric: [] as string[], categorical: [] as string[], dateLike: [] as string[] };
  const cols = Object.keys(data[0]);
  const sample = data.slice(0, 20);
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
      lower.includes("time") ||
      /trade_date|calc_date|updated_at/.test(lower)
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
  const x =
    dateLike[0] ||
    categorical.find((c) => !/id$/i.test(c)) ||
    categorical[0] ||
    Object.keys(data[0] || {})[0];
  const yCols = numeric.filter((c) => c !== x).slice(0, 3);
  return { x, yCols, dateLike };
}
