"use client";

import { useEffect, useState } from "react";

interface DivergentTicker {
  ticker: string;
  company_name: string;
  days_divergent: number;
  avg_diff_pct: number | null;
  max_diff_pct: number | null;
  latest_date: string;
}

interface DivergentByDate {
  trade_date: string;
  divergent_count: number;
  max_diff_pct: number | null;
}

interface DataQuality {
  last_checked: string | null;
  summary: Record<string, number>;
  top_divergent_tickers: DivergentTicker[];
  divergent_by_date: DivergentByDate[];
}

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

async function fetchDataQuality(domainId = "finance_vnfdata"): Promise<DataQuality> {
  const res = await fetch(
    `${API_BASE}/api/v1/data-quality?domain_id=${domainId}`,
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

function severityColor(pct: number | null): string {
  if (pct == null) return "text-ink-soft";
  if (pct >= 20) return "text-red-600";
  if (pct >= 10) return "text-copper";
  if (pct >= 5) return "text-amber-500";
  return "text-teal";
}

function severityBadge(pct: number | null): string {
  if (pct == null) return "bg-mist text-ink-soft";
  if (pct >= 20) return "bg-red-50 text-red-600 border-red-200";
  if (pct >= 10) return "bg-copper-soft/40 text-copper border-copper/30";
  if (pct >= 5) return "bg-amber-50 text-amber-600 border-amber-200";
  return "bg-teal/8 text-teal border-teal/25";
}

export default function DataQualityPage() {
  const [data, setData] = useState<DataQuality | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchDataQuality()
      .then(setData)
      .catch((e) => setError(String(e)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-ink-soft">
        Đang tải…
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex min-h-dvh items-center justify-center text-copper">
        Lỗi: {error || "Không có dữ liệu"}
      </div>
    );
  }

  const verified = data.summary["verified"] ?? 0;
  const divergent = data.summary["divergent"] ?? 0;
  const total = verified + divergent;
  const qualityPct = total > 0 ? ((verified / total) * 100).toFixed(1) : "—";

  return (
    <div className="min-h-dvh bg-foam px-4 py-8 md:px-8">
      <div className="mx-auto max-w-5xl space-y-8">
        {/* Header */}
        <div>
          <h1 className="font-[family-name:var(--font-display)] text-2xl font-bold text-ink">
            Data Quality · Giá đóng cửa
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            Cross-check từ nhiều nguồn (VFS · VCI · KBS) —{" "}
            {data.last_checked
              ? `cập nhật lúc ${new Date(data.last_checked).toLocaleString("vi-VN")}`
              : "chưa có thông tin cập nhật"}
          </p>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {[
            { label: "Tổng records check", value: total.toLocaleString("vi-VN"), accent: "#0f766e" },
            { label: "Verified ✓", value: verified.toLocaleString("vi-VN"), accent: "#0f766e" },
            {
              label: "Divergent ✗",
              value: divergent.toLocaleString("vi-VN"),
              accent: divergent > 0 ? "#b45309" : "#0f766e",
            },
            {
              label: "Tỷ lệ chính xác",
              value: `${qualityPct}%`,
              accent: Number(qualityPct) >= 99 ? "#0f766e" : "#b45309",
            },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className="relative overflow-hidden rounded-xl border border-line bg-white px-4 py-3"
            >
              <div
                className="absolute inset-x-0 top-0 h-[3px]"
                style={{ background: kpi.accent }}
              />
              <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-soft/65">
                {kpi.label}
              </p>
              <p className="mt-1.5 font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-ink">
                {kpi.value}
              </p>
            </div>
          ))}
        </div>

        {/* Divergent by date */}
        {data.divergent_by_date.length > 0 && (
          <div className="rounded-xl border border-line bg-white p-5">
            <h2 className="mb-4 text-sm font-semibold text-ink">
              Divergent theo ngày · 30 ngày gần nhất
            </h2>
            <div className="space-y-1.5">
              {data.divergent_by_date.map((row) => {
                const barPct = Math.min(
                  100,
                  (row.divergent_count /
                    Math.max(...data.divergent_by_date.map((r) => r.divergent_count))) *
                    100,
                );
                return (
                  <div key={row.trade_date} className="flex items-center gap-3">
                    <span className="w-24 shrink-0 text-right text-xs text-ink-soft">
                      {row.trade_date}
                    </span>
                    <div className="relative h-5 flex-1 overflow-hidden rounded bg-mist">
                      <div
                        className="absolute inset-y-0 left-0 rounded bg-copper/70"
                        style={{ width: `${barPct}%` }}
                      />
                      <span className="absolute inset-0 flex items-center px-2 text-[11px] font-semibold text-ink">
                        {row.divergent_count} mã
                      </span>
                    </div>
                    {row.max_diff_pct != null && (
                      <span
                        className={`w-16 shrink-0 text-xs font-medium ${severityColor(row.max_diff_pct)}`}
                      >
                        max {row.max_diff_pct.toFixed(1)}%
                      </span>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Top divergent tickers table */}
        <div className="rounded-xl border border-line bg-white">
          <div className="border-b border-line px-5 py-4">
            <h2 className="text-sm font-semibold text-ink">
              Top mã lệch nhiều ngày nhất
            </h2>
            <p className="mt-0.5 text-xs text-ink-soft">
              Sorted by số ngày divergent — mã lệch nhiều ngày liên tục thường
              do nguồn dữ liệu chưa điều chỉnh corporate action
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line bg-mist/50 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-soft">
                  <th className="px-5 py-2.5">Mã</th>
                  <th className="px-3 py-2.5">Công ty</th>
                  <th className="px-3 py-2.5 text-right">Số ngày lệch</th>
                  <th className="px-3 py-2.5 text-right">TB lệch</th>
                  <th className="px-3 py-2.5 text-right">Max lệch</th>
                  <th className="px-5 py-2.5 text-right">Ngày gần nhất</th>
                </tr>
              </thead>
              <tbody>
                {data.top_divergent_tickers.map((row, i) => (
                  <tr
                    key={row.ticker}
                    className={`border-b border-line/60 transition-colors hover:bg-foam/60 ${
                      i % 2 === 0 ? "" : "bg-mist/20"
                    }`}
                  >
                    <td className="px-5 py-2.5">
                      <span className="font-[family-name:var(--font-display)] font-semibold text-ink">
                        {row.ticker}
                      </span>
                    </td>
                    <td className="max-w-[220px] truncate px-3 py-2.5 text-ink-soft">
                      {row.company_name}
                    </td>
                    <td className="px-3 py-2.5 text-right font-semibold text-ink">
                      {row.days_divergent}
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${severityBadge(row.avg_diff_pct)}`}
                      >
                        {row.avg_diff_pct != null
                          ? `${row.avg_diff_pct.toFixed(1)}%`
                          : "—"}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-right">
                      <span
                        className={`inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-semibold ${severityBadge(row.max_diff_pct)}`}
                      >
                        {row.max_diff_pct != null
                          ? `${row.max_diff_pct.toFixed(1)}%`
                          : "—"}
                      </span>
                    </td>
                    <td className="px-5 py-2.5 text-right text-xs text-ink-soft">
                      {row.latest_date}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-3 text-xs text-ink-soft">
          <span className="font-semibold">Mức độ lệch:</span>
          {[
            { label: "< 5%", cls: "bg-teal/8 text-teal border-teal/25" },
            { label: "5–10%", cls: "bg-amber-50 text-amber-600 border-amber-200" },
            { label: "10–20%", cls: "bg-copper-soft/40 text-copper border-copper/30" },
            { label: "≥ 20%", cls: "bg-red-50 text-red-600 border-red-200" },
          ].map((b) => (
            <span
              key={b.label}
              className={`inline-flex items-center rounded-full border px-2 py-0.5 font-semibold ${b.cls}`}
            >
              {b.label}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
