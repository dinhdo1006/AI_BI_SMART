export function friendlyLabel(
  col: string,
  labels?: Record<string, string> | null,
): string {
  if (labels?.[col]) return labels[col];
  return col.replace(/_/g, " ");
}

export function formatNumber(value: unknown, colName = ""): string {
  const n = typeof value === "number" ? value : Number(value);
  if (!Number.isFinite(n)) return value == null ? "—" : String(value);

  const lower = colName.toLowerCase();
  // Chỉ % cho field % thật — KHÔNG gắn % cho pe_ratio / pb_ratio
  const isPercent =
    /(^|_)(pct|percent)(_|$)/.test(lower) ||
    /change_percent|completion_pct|free_float_pct/.test(lower) ||
    /^(roe|roa)$/.test(lower) ||
    lower === "roe" ||
    lower === "roa";

  if (isPercent) {
    return `${n.toLocaleString("vi-VN", { maximumFractionDigits: 2 })}%`;
  }
  if (Math.abs(n) >= 1_000_000_000) {
    return `${(n / 1_000_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tỷ`;
  }
  if (Math.abs(n) >= 1_000_000) {
    return `${(n / 1_000_000).toLocaleString("vi-VN", { maximumFractionDigits: 2 })} tr`;
  }
  if (Number.isInteger(n)) return n.toLocaleString("vi-VN");
  return n.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
}

export function downloadCsv(
  rows: Record<string, unknown>[],
  filename = "bi_export.csv",
) {
  if (!rows.length) return;
  const cols = Object.keys(rows[0]);
  const esc = (v: unknown) => {
    const s = v == null ? "" : String(v);
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  const body = [
    cols.join(","),
    ...rows.map((r) => cols.map((c) => esc(r[c])).join(",")),
  ].join("\n");
  const blob = new Blob(["\uFEFF" + body], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadText(content: string, filename: string, mime: string) {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
