import { formatAxisLabel } from "./format";
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

function entityColumn(categorical: string[]): string | undefined {
  return (
    categorical.find((c) => ENTITY_COL.test(c)) ||
    categorical.find((c) => !/id$/i.test(c))
  );
}

/** Long format: nhiều mã × nhiều ngày (mỗi mã ≥2 phiên). */
export function isLongFormatTimeSeries(
  data: Record<string, unknown>[],
  entity?: string,
  dateCol?: string,
): boolean {
  if (!data.length || !entity || !dateCol) return false;
  const entities = uniqueCount(data, entity);
  const dates = uniqueCount(data, dateCol);
  if (entities < 2 || dates < 2) return false;
  return data.length / entities >= 1.5;
}

export function pickChartAxes(data: Record<string, unknown>[]) {
  const { numeric, categorical, dateLike } = analyzeColumns(data);
  const entity = entityColumn(categorical);
  const dateCol = dateLike[0];

  let x: string | undefined;

  // Long format entity × ngày → luôn ưu tiên ngày làm trục X
  if (isLongFormatTimeSeries(data, entity, dateCol)) {
    x = dateCol;
  }

  // Snapshot so sánh nhiều mã (không phải chuỗi thời gian dài)
  if (!x && entity && uniqueCount(data, entity) >= 2) {
    if (!dateCol || uniqueCount(data, dateCol) <= uniqueCount(data, entity)) {
      x = entity;
    }
  }

  // Chuỗi thời gian đơn entity
  if (!x && dateCol && uniqueCount(data, dateCol) >= 3) {
    x = dateCol;
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

export const MAX_GROUPBY_SERIES = 12;

export type ChartSeriesMode = "columns" | "groupBy";

export type BarDisplayMode = "group" | "stack100";

export type WaterfallDisplayMode = "ranking" | "bridge" | "composition";

export type ChartPlan = {
  mode: ChartSeriesMode;
  x: string;
  yCols: string[];
  groupBy?: string;
  seriesKeys: string[];
  isTimeSeries: boolean;
  isComparison: boolean;
  entity?: string;
  barMode?: BarDisplayMode;
  hint?: string;
};

const STACKED_100_KEYWORDS =
  /(tỷ\s*trọng|ty\s*trong|cơ\s*cấu|co\s*cau|new\s*vs|repeat|phần\s*trăm|phan\s*tram|100\s*%|stacked|chồng|chong|tỉ\s*lệ|ti\s*le|so\s*sánh\s*tỷ|so\s*sanh\s*ty)/i;

const WATERFALL_BRIDGE_KEYWORDS =
  /(đóng\s*góp|dong\s*gop|bridge|thác|thac|waterfall|biến\s*động|bien\s*dong|tăng\s*giảm|tang\s*giam|delta)/i;

export function shouldUseStacked100Percent(
  data: Record<string, unknown>[],
  yCols: string[],
  categoryCol: string | undefined,
  userQuery = "",
): boolean {
  if (!data.length || !categoryCol || yCols.length !== 2) return false;
  if (!STACKED_100_KEYWORDS.test(userQuery)) return false;
  const positives = data.filter((row) => {
    const a = Number(row[yCols[0]]);
    const b = Number(row[yCols[1]]);
    return Number.isFinite(a) && Number.isFinite(b) && a >= 0 && b >= 0;
  });
  return positives.length >= Math.max(1, Math.floor(data.length * 0.7));
}

/** Gom 1 dòng / entity (kỳ mới nhất nếu có ngày). */
export function dedupeRowsByEntity(
  data: Record<string, unknown>[],
  entityKey: string,
): Record<string, unknown>[] {
  if (!data.length) return [];
  const dateCol = Object.keys(data[0] ?? {}).find((c) =>
    /date|ngay|trade_date|calc_date|period/i.test(c),
  );
  if (dateCol) return dedupeLatestPerEntity(data, entityKey, dateCol);

  const byEntity = new Map<string, Record<string, unknown>>();
  for (const row of data) {
    const key = String(row[entityKey] ?? "");
    if (!byEntity.has(key)) byEntity.set(key, row);
  }
  return byEntity.size < data.length ? [...byEntity.values()] : data;
}

export function detectWaterfallMode(
  values: number[],
  userQuery = "",
): WaterfallDisplayMode {
  if (values.some((v) => v < 0)) return "bridge";
  if (WATERFALL_BRIDGE_KEYWORDS.test(userQuery)) return "composition";
  return "ranking";
}

/** Chuẩn hóa 2 metric thành % trên từng category (stacked 100%). */
export function toStack100Rows(
  rows: Record<string, unknown>[],
  yCols: [string, string],
): Record<string, unknown>[] {
  return rows.map((row) => {
    const a = Number(row[yCols[0]]) || 0;
    const b = Number(row[yCols[1]]) || 0;
    const sum = a + b;
    const out = { ...row };
    out[yCols[0]] = sum > 0 ? (a / sum) * 100 : 0;
    out[yCols[1]] = sum > 0 ? (b / sum) * 100 : 0;
    return out;
  });
}

function dedupeLatestPerEntity(
  data: Record<string, unknown>[],
  entityKey: string,
  dateKey: string,
): Record<string, unknown>[] {
  const byEntity = new Map<string, Record<string, unknown>>();
  for (const row of data) {
    const key = String(row[entityKey] ?? "");
    const prev = byEntity.get(key);
    if (!prev || String(row[dateKey] ?? "") > String(prev[dateKey] ?? "")) {
      byEntity.set(key, row);
    }
  }
  return byEntity.size < data.length ? [...byEntity.values()] : data;
}

function reshapeGroupByTimeSeries(
  data: Record<string, unknown>[],
  xKey: string,
  groupBy: string,
  yCol: string,
  seriesKeys: string[],
): Record<string, unknown>[] {
  const xValues = [
    ...new Set(data.map((r) => String(r[xKey] ?? ""))),
  ].sort((a, b) => a.localeCompare(b));

  return xValues.map((xVal) => {
    const point: Record<string, unknown> = {
      name: formatAxisLabel(xVal, xKey),
    };
    for (const ent of seriesKeys) {
      const row = data.find(
        (r) => String(r[xKey] ?? "") === xVal && String(r[groupBy] ?? "") === ent,
      );
      const n = row ? Number(row[yCol]) : NaN;
      point[ent] = Number.isFinite(n) ? n : null;
    }
    return point;
  });
}

/** Lập kế hoạch reshape + series trước khi vẽ. */
export function buildChartPlan(
  data: Record<string, unknown>[],
  chartType: ChartType,
  userQuery = "",
): ChartPlan | null {
  if (!data.length) return null;

  const axes = pickChartAxes(data);
  const { x, yCols, dateLike, isTimeSeries, isComparison, entity } = axes;
  if (!x || !yCols.length) return null;

  const effective = refineChartType(chartType, data, userQuery);
  const dateCol = dateLike[0];
  const longTs = isLongFormatTimeSeries(data, entity, dateCol);

  if (
    longTs &&
    entity &&
    dateCol &&
    (effective === "line" ||
      effective === "area" ||
      effective === "bar" ||
      effective === "combo")
  ) {
    const entities = [
      ...new Set(data.map((r) => String(r[entity] ?? "")).filter(Boolean)),
    ].sort();
    const limited = entities.slice(0, MAX_GROUPBY_SERIES);
    const truncated = entities.length > MAX_GROUPBY_SERIES;
    return {
      mode: "groupBy",
      x: dateCol,
      yCols: [yCols[0]],
      groupBy: entity,
      seriesKeys: limited,
      isTimeSeries: true,
      isComparison: false,
      entity,
      hint: truncated
        ? `Mỗi mã một chuỗi · hiển thị ${limited.length}/${entities.length} mã`
        : `Mỗi mã một chuỗi (${entities.length} mã)`,
    };
  }

  const useStack100 =
    effective === "bar" &&
    !isTimeSeries &&
    shouldUseStacked100Percent(data, yCols, x, userQuery);

  if (useStack100 && yCols.length === 2) {
    return {
      mode: "columns",
      x,
      yCols: [yCols[0], yCols[1]],
      seriesKeys: [yCols[0], yCols[1]],
      isTimeSeries: false,
      isComparison: true,
      entity,
      barMode: "stack100",
      hint: "Cột chồng 100% — so sánh tỷ trọng 2 thành phần",
    };
  }

  if (isComparison && yCols.length >= 2) {
    return {
      mode: "columns",
      x,
      yCols,
      seriesKeys: yCols,
      isTimeSeries,
      isComparison: true,
      entity,
      barMode: "group",
      hint: `Cột nhóm · so sánh ${yCols.length} chỉ số trên ${uniqueCount(data, x)} mục`,
    };
  }

  return {
    mode: "columns",
    x,
    yCols,
    seriesKeys: yCols,
    isTimeSeries,
    isComparison,
    entity,
    barMode: effective === "bar" ? "group" : undefined,
  };
}

/** Chuẩn hóa dữ liệu theo ChartPlan (sort, dedupe, pivot long→wide). */
export function reshapeForChart(
  data: Record<string, unknown>[],
  plan: ChartPlan,
): Record<string, unknown>[] {
  if (plan.mode === "groupBy" && plan.groupBy) {
    return reshapeGroupByTimeSeries(
      data,
      plan.x,
      plan.groupBy,
      plan.yCols[0],
      plan.seriesKeys,
    );
  }

  let rows = [...data];
  const dateCol = rows[0]
    ? Object.keys(rows[0]).find((c) =>
        /date|ngay|trade_date|calc_date/i.test(c),
      )
    : undefined;

  if (plan.isComparison && plan.entity && dateCol) {
    rows = dedupeLatestPerEntity(rows, plan.entity, dateCol);
  }

  if (plan.isTimeSeries) {
    rows.sort((a, b) =>
      String(a[plan.x] ?? "").localeCompare(String(b[plan.x] ?? "")),
    );
  }

  if (plan.barMode === "stack100" && plan.yCols.length === 2) {
    const pair = [plan.yCols[0], plan.yCols[1]] as [string, string];
    rows = toStack100Rows(rows, pair);
  }

  return rows.map((row) => {
    const point: Record<string, unknown> = {
      name: formatAxisLabel(row[plan.x], plan.x),
    };
    for (const y of plan.yCols) {
      const n = Number(row[y]);
      point[y] = Number.isFinite(n) ? n : null;
    }
    return point;
  });
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
    const col =
      categorical.find((c) => c !== row && !ENTITY_COL.test(c)) ??
      categorical.find((c) => c !== row);
    if (
      col &&
      !isBadHeatmapPivot(row, col) &&
      uniqueCount(data, row) >= 2 &&
      uniqueCount(data, col) >= 2
    ) {
      return { mode: "pivot", row, col, value: preferred[0] };
    }
  }

  return null;
}

/** Pivot vô nghĩa: mã × tên công ty (1:1, ma trận chéo thưa). */
export function isBadHeatmapPivot(row: string, col: string): boolean {
  if (ENTITY_COL.test(row) && ENTITY_COL.test(col)) return true;
  const r = row.toLowerCase();
  const c = col.toLowerCase();
  const isCode = /ticker|symbol|ma_cp|ma\s*cp/.test(r);
  const isName = /company|short_name|ten_cong_ty/.test(c);
  const isCodeCol = /ticker|symbol|ma_cp|ma\s*cp/.test(c);
  const isNameRow = /company|short_name|ten_cong_ty/.test(r);
  return (isCode && isName) || (isCodeCol && isNameRow);
}

/** Giới hạn số hàng metrics heatmap — 1 hàng/mã (kỳ mới nhất), tối đa limit. */
export function prepareHeatmapMetricRows(
  data: Record<string, unknown>[],
  entityKey: string,
  metricKeys: string[],
  limit = CHART_DENSE_THRESHOLDS.heatmapMetricsMaxRows,
): { rows: Record<string, unknown>[]; truncated: boolean } {
  if (!data.length) return { rows: [], truncated: false };

  const dateCol = Object.keys(data[0] ?? {}).find((c) =>
    /date|ngay|trade_date|calc_date|period/i.test(c),
  );

  const byEntity = new Map<string, Record<string, unknown>>();
  for (const row of data) {
    const key = String(row[entityKey] ?? "");
    const prev = byEntity.get(key);
    if (!prev) {
      byEntity.set(key, row);
      continue;
    }
    if (!dateCol) continue;
    if (
      String(row[dateCol] ?? "").localeCompare(String(prev[dateCol] ?? "")) > 0
    ) {
      byEntity.set(key, row);
    }
  }

  let rows = Array.from(byEntity.values());
  if (dateCol) {
    rows.sort((a, b) =>
      String(b[dateCol] ?? "").localeCompare(String(a[dateCol] ?? "")),
    );
  }

  const truncated = rows.length > limit;
  if (truncated) rows = rows.slice(0, limit);
  return { rows, truncated };
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
  const ranked = [...numeric].sort(
    (a, b) => metricScore(b) - metricScore(a),
  );
  // Ưu tiên nhóm cùng bậc (P/E·P/B·ROE) — tránh lẫn vốn hóa làm radar lệch hình
  let metrics = selectCompatibleYCols(data, ranked).slice(0, 6);
  if (metrics.length < 3) metrics = ranked.slice(0, 5);
  if (!entity || metrics.length < 3) return null;

  const deduped = dedupeRowsByEntity(data, entity);
  if (uniqueCount(deduped, entity) < 2 || deduped.length > 12) return null;
  return { entity, metrics };
}

export type WaterfallAxes = {
  category: string;
  value: string;
  mode: WaterfallDisplayMode;
};

export function pickWaterfallAxes(
  data: Record<string, unknown>[],
  userQuery = "",
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
  const values = data.map((r) => {
    const n = Number(r[preferred[0]]);
    return Number.isFinite(n) ? n : 0;
  });
  return {
    category,
    value: preferred[0],
    mode: detectWaterfallMode(values, userQuery),
  };
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
  userQuery = "",
): ChartType {
  if (requested === "table") return "table";

  if (requested === "candlestick") {
    return detectOhlcColumns(data) ? "candlestick" : "line";
  }

  if (requested === "heatmap") {
    if (pickHeatmapAxes(data)) return "heatmap";
    if (pickRadarAxes(data)) return "radar";
    return "bar";
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
    return pickWaterfallAxes(data, userQuery) ? "waterfall" : "bar";
  }

  const { yCols } = pickChartAxes(data);

  if (requested === "combo" && yCols.length < 2) return "bar";

  // Không ép bar → radar: lựa chọn của user (dropdown / «Thử») phải được tôn trọng.
  // Template «So sánh định giá» đã set chart_type=radar sẵn.

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
    return refined === "radar"
      ? "Heatmap không phù hợp — đã chuyển sang radar (so sánh chỉ số)."
      : "Thiếu ma trận phù hợp — đã chuyển sang cột.";
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
  heatmapPivotMaxDim: 36,
  heatmapMetricsMaxRows: 20,
  heatmapRowHeight: 30,
  heatmapMinHeight: 280,
  heatmapMaxHeight: 720,
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

/** Nhãn tiếng Việt cho loại biểu đồ. */
export const CHART_TYPE_LABELS: Record<ChartType, string> = {
  bar: "Biểu đồ cột",
  line: "Biểu đồ đường",
  area: "Biểu đồ miền",
  pie: "Biểu đồ tròn",
  combo: "Biểu đồ combo",
  candlestick: "Biểu đồ nến",
  heatmap: "Heatmap",
  scatter: "Biểu đồ phân tán",
  treemap: "Treemap",
  radar: "Biểu đồ radar",
  waterfall: "Biểu đồ thác nước",
  table: "Bảng số liệu",
};

export type ChartChoiceExplanation = {
  chartLabel: string;
  effectiveType: ChartType;
  message: string;
  alternatives: { type: ChartType; label: string; reason: string }[];
};

const ALT_CHART_REASONS: Partial<Record<ChartType, string>> = {
  line: "Xem xu hướng theo thời gian",
  bar: "So sánh / xếp hạng trực quan",
  radar: "So sánh nhiều chỉ số trên vài mã",
  scatter: "Khám phá tương quan 2 chỉ số",
  table: "Xem đầy đủ số liệu",
  treemap: "Nhiều danh mục — ưu tiên theo quy mô",
  heatmap: "Ma trận mã × thời gian",
};

/** Giải thích vì sao chọn loại biểu đồ + gợi ý thay thế. */
export function explainChartChoice(
  chartType: ChartType,
  data: Record<string, unknown>[],
  userQuery = "",
): ChartChoiceExplanation | null {
  if (!data.length || chartType === "table") return null;

  const effective = refineChartType(chartType, data, userQuery);
  const plan = buildChartPlan(data, effective, userQuery);
  const refineHint = chartTypeHint(chartType, data);

  let message =
    plan?.hint ||
    refineHint ||
    defaultChartMessage(effective, data, plan);

  if (chartType !== effective && refineHint) {
    message = refineHint;
  } else if (plan?.hint) {
    message = `Đã chọn ${CHART_TYPE_LABELS[effective].toLowerCase()} — ${plan.hint}`;
  } else {
    message = `Đã chọn ${CHART_TYPE_LABELS[effective].toLowerCase()} — ${message}`;
  }

  const allowed = compatibleCharts(data);
  const alternatives: ChartChoiceExplanation["alternatives"] = [];
  const priority: ChartType[] = [
    "line",
    "bar",
    "radar",
    "scatter",
    "table",
    "treemap",
    "heatmap",
  ];

  for (const t of priority) {
    // Loại trừ cả lựa chọn user và loại đang hiển thị (sau refine)
    if (t === chartType || t === effective || !allowed.includes(t)) continue;
    alternatives.push({
      type: t,
      label: CHART_TYPE_LABELS[t],
      reason: ALT_CHART_REASONS[t] || "Phù hợp với dữ liệu hiện tại",
    });
    if (alternatives.length >= 2) break;
  }

  return {
    chartLabel: CHART_TYPE_LABELS[effective],
    effectiveType: effective,
    message,
    alternatives,
  };
}

function defaultChartMessage(
  effective: ChartType,
  data: Record<string, unknown>[],
  plan: ChartPlan | null,
): string {
  if (plan?.mode === "groupBy") return "mỗi mã một chuỗi thời gian";
  const { isTimeSeries, isComparison, yCols } = pickChartAxes(data);
  if (effective === "line" && isTimeSeries) return "diễn biến theo thời gian";
  if (effective === "bar" && isComparison)
    return `so sánh ${yCols.length} chỉ số`;
  if (effective === "radar") return "so sánh đa chỉ số giữa các mã";
  if (effective === "scatter") return "mối quan hệ giữa hai chỉ số";
  if (effective === "heatmap") return "ma trận giá trị theo mã và thời gian";
  return "phù hợp với hình dạng dữ liệu";
}

const PIN_COL =
  /^(ticker|symbol|ma_cp|ma\s*cp|trade_date|calc_date|date|ngay|company_name|short_name)$/i;

/** Sắp xếp cột bảng: pin entity/ngày trước, metric quan trọng sau. */
export function orderTableColumns(cols: string[]): {
  ordered: string[];
  pinned: string[];
} {
  const pinned = cols.filter((c) => PIN_COL.test(c));
  const rest = cols.filter((c) => !pinned.includes(c));
  rest.sort((a, b) => metricScore(b) - metricScore(a));
  return { ordered: [...pinned, ...rest], pinned };
}

/** Sort mặc định cho bảng số liệu. */
export function pickDefaultTableSort(
  data: Record<string, unknown>[],
): { col: string; dir: "asc" | "desc" } | null {
  if (!data.length) return null;
  const { yCols, entity, isTimeSeries, dateLike } = pickChartAxes(data);
  if (isTimeSeries && dateLike[0]) {
    return { col: dateLike[0], dir: "desc" };
  }
  if (yCols[0]) return { col: yCols[0], dir: "desc" };
  if (entity) return { col: entity, dir: "asc" };
  const first = Object.keys(data[0])[0];
  return first ? { col: first, dir: "asc" } : null;
}
