"use client";

import { formatNumber, friendlyLabel } from "@/lib/format";
import { analyzeColumns } from "@/lib/viz";

const ACCENTS = ["#0f766e", "#b45309", "#1c3a4a", "#0e7490"];

export function KpiRow({
  data,
  labels,
}: {
  data: Record<string, unknown>[];
  labels?: Record<string, string>;
}) {
  if (!data.length) return null;
  const { numeric } = analyzeColumns(data);
  const cols = numeric.slice(0, 4);
  if (!cols.length) return null;

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
    return {
      label: friendlyLabel(col, labels),
      value: formatNumber(useSum ? sum : avg, col),
      hint: useSum ? "Tổng" : "TB",
    };
  });

  return (
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
        </div>
      ))}
    </div>
  );
}
