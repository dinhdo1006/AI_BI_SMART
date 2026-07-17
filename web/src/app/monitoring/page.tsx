"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { fetchAlertEvents, fetchMonitoringMetrics } from "@/lib/api";
import type { AlertEvent } from "@/lib/types";

type Metrics = {
  total_requests: number;
  hours: number;
  success_rate: number;
  error_rate: number;
  cache_hit_rate: number;
  avg_latency_ms: number;
  p95_latency_ms: number;
  p99_latency_ms: number;
  sql_source_breakdown: Record<string, number>;
  intent_breakdown: Record<string, number>;
  requests_by_hour: Record<string, number>;
  top_queries: Array<{ query: string; count: number }>;
};

async function loadMetrics(hours: number): Promise<Metrics | null> {
  return fetchMonitoringMetrics(hours);
}

function askFromEvent(ev: AlertEvent): string {
  return (
    ev.payload?.suggested_query ||
    (ev.target
      ? `Phân tích ${ev.target} liên quan ${ev.metric_key} (ngưỡng ${ev.operator} ${ev.threshold})`
      : `Giải thích alert ${ev.rule_name}: ${ev.message}`)
  );
}

function goAskInChat(query: string) {
  try {
    sessionStorage.setItem("abi_suggest", query);
  } catch {
    /* ignore */
  }
  window.location.href = "/";
}

function KpiCard({
  label,
  value,
  unit = "",
  color = "text-teal",
}: {
  label: string;
  value: string | number;
  unit?: string;
  color?: string;
}) {
  return (
    <div className="rounded-xl border border-line bg-white/95 p-5 shadow-sm">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ink-soft/60">
        {label}
      </p>
      <p className={`mt-1 text-3xl font-extrabold ${color}`}>
        {value}
        {unit && (
          <span className="ml-1 text-base font-normal text-ink-soft">{unit}</span>
        )}
      </p>
    </div>
  );
}

function BreakdownTable({
  title,
  data,
}: {
  title: string;
  data: Record<string, number>;
}) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (!entries.length) return null;
  return (
    <div className="rounded-xl border border-line bg-white/95 p-5 shadow-sm">
      <p className="mb-3 text-sm font-bold text-ink">{title}</p>
      <div className="space-y-2">
        {entries.map(([key, count]) => (
          <div key={key} className="flex items-center gap-3">
            <span className="w-36 truncate text-xs text-ink-soft">{key}</span>
            <div className="flex-1 overflow-hidden rounded-full bg-foam">
              <div
                className="h-2 rounded-full bg-teal"
                style={{ width: `${Math.round((count / total) * 100)}%` }}
              />
            </div>
            <span className="w-12 text-right text-xs font-semibold text-ink">
              {count}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function MonitoringPage() {
  const [hours, setHours] = useState(24);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [alertEvents, setAlertEvents] = useState<AlertEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([loadMetrics(hours), fetchAlertEvents(null, 30)]).then(
      ([m, events]) => {
        if (cancelled) return;
        if (!m) setError("Không tải được metrics. Đảm bảo đăng nhập admin.");
        else {
          setError(null);
          setMetrics(m);
        }
        setAlertEvents(events);
        setLoading(false);
      },
    );
    return () => {
      cancelled = true;
    };
  }, [hours]);

  return (
    <div className="min-h-dvh bg-foam/40 px-4 py-8 md:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-teal">
            Admin
          </p>
          <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl font-extrabold text-ink">
            Monitoring Dashboard
          </h1>
          <p className="mt-1 text-sm text-ink-soft">
            Theo dõi request + lịch sử alert — bấm hỏi lại để nối sang chat.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="rounded-lg border border-line bg-white px-3 py-1 text-sm font-semibold text-ink hover:bg-foam"
          >
            ← Chat
          </Link>
          <label className="text-xs text-ink-soft">Khoảng thời gian:</label>
          <select
            value={hours}
            onChange={(e) => {
              setLoading(true);
              setHours(Number(e.target.value));
            }}
            className="rounded-lg border border-line bg-white px-2 py-1 text-sm text-ink"
          >
            <option value={1}>1 giờ</option>
            <option value={6}>6 giờ</option>
            <option value={24}>24 giờ</option>
            <option value={72}>3 ngày</option>
            <option value={168}>7 ngày</option>
          </select>
          <button
            onClick={() => {
              setLoading(true);
              void Promise.all([
                loadMetrics(hours),
                fetchAlertEvents(null, 30),
              ]).then(([m, events]) => {
                if (m) {
                  setError(null);
                  setMetrics(m);
                } else {
                  setError("Không tải được metrics. Đảm bảo đăng nhập admin.");
                }
                setAlertEvents(events);
                setLoading(false);
              });
            }}
            className="rounded-lg border border-line bg-white px-3 py-1 text-sm font-semibold text-ink hover:bg-foam"
          >
            ↻ Làm mới
          </button>
        </div>
      </div>

      {error && (
        <p className="mb-4 rounded-xl border border-copper/25 bg-copper-soft/30 p-3 text-sm text-copper">
          {error}
        </p>
      )}

      {loading ? (
        <p className="text-sm text-ink-soft">Đang tải metrics…</p>
      ) : metrics ? (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-6">
            <KpiCard label="Tổng request" value={metrics.total_requests} />
            <KpiCard
              label="Thành công"
              value={`${metrics.success_rate}%`}
              color="text-teal"
            />
            <KpiCard
              label="Lỗi"
              value={`${metrics.error_rate}%`}
              color={metrics.error_rate > 10 ? "text-copper" : "text-ink-soft"}
            />
            <KpiCard
              label="Cache hit"
              value={`${metrics.cache_hit_rate}%`}
              color="text-teal"
            />
            <KpiCard
              label="Avg latency"
              value={metrics.avg_latency_ms}
              unit="ms"
              color={metrics.avg_latency_ms > 5000 ? "text-copper" : "text-ink"}
            />
            <KpiCard
              label="P95 latency"
              value={metrics.p95_latency_ms}
              unit="ms"
              color={metrics.p95_latency_ms > 10000 ? "text-copper" : "text-ink"}
            />
          </div>

          <div className="rounded-xl border border-line bg-white/95 p-5 shadow-sm">
            <div className="mb-3 flex items-center justify-between gap-2">
              <p className="text-sm font-bold text-ink">
                Lịch sử alert ({alertEvents.length})
              </p>
              <span className="text-[11px] text-ink-soft/60">
                Event ID = tham chiếu phân tích tiếp
              </span>
            </div>
            {alertEvents.length === 0 ? (
              <p className="text-sm text-ink-soft">
                Chưa có event — tạo rule ở sidebar và bấm «Kiểm tra ngay».
              </p>
            ) : (
              <div className="divide-y divide-line">
                {alertEvents.map((ev) => {
                  const when = (() => {
                    try {
                      return new Date(ev.triggered_at).toLocaleString("vi-VN");
                    } catch {
                      return ev.triggered_at;
                    }
                  })();
                  return (
                    <div
                      key={ev.id}
                      className="flex flex-wrap items-start justify-between gap-3 py-3"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="rounded-md bg-copper-soft/50 px-1.5 py-0.5 font-mono text-[10px] text-copper">
                            #{ev.id.slice(0, 8)}
                          </span>
                          <span className="text-xs font-semibold text-ink">
                            {ev.rule_name}
                          </span>
                          <span className="text-[11px] text-ink-soft/55">
                            {ev.domain_id}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-ink">{ev.message}</p>
                        <p className="mt-0.5 text-[11px] text-ink-soft/55">
                          {when} · {ev.metric_key}
                          {ev.target ? ` · ${ev.target}` : ""} · giá trị{" "}
                          {ev.value}
                        </p>
                      </div>
                      <button
                        type="button"
                        onClick={() => goAskInChat(askFromEvent(ev))}
                        className="shrink-0 rounded-lg bg-teal px-3 py-1.5 text-xs font-semibold text-white hover:bg-teal-deep"
                      >
                        Hỏi lại trong chat →
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          <div className="grid gap-5 md:grid-cols-2">
            <BreakdownTable
              title="SQL Source Breakdown"
              data={metrics.sql_source_breakdown}
            />
            <BreakdownTable
              title="Intent Breakdown"
              data={metrics.intent_breakdown}
            />
          </div>

          {Object.keys(metrics.requests_by_hour).length > 0 && (
            <div className="rounded-xl border border-line bg-white/95 p-5 shadow-sm">
              <p className="mb-3 text-sm font-bold text-ink">
                Requests theo giờ (24h gần nhất)
              </p>
              <div className="flex items-end gap-1 overflow-x-auto pb-2">
                {Object.entries(metrics.requests_by_hour)
                  .slice(-24)
                  .map(([h, c]) => {
                    const maxVal = Math.max(
                      ...Object.values(metrics.requests_by_hour),
                    );
                    const pct = maxVal > 0 ? (c / maxVal) * 100 : 0;
                    return (
                      <div
                        key={h}
                        className="flex flex-col items-center gap-1"
                        title={`${h}: ${c} requests`}
                      >
                        <div
                          className="w-6 rounded-t bg-teal/70"
                          style={{
                            height: `${Math.max(pct, 2)}px`,
                            maxHeight: "80px",
                          }}
                        />
                        <span className="text-[9px] text-ink-soft/50 rotate-45">
                          {h.slice(11, 16)}
                        </span>
                      </div>
                    );
                  })}
              </div>
            </div>
          )}

          {metrics.top_queries.length > 0 && (
            <div className="rounded-xl border border-line bg-white/95 p-5 shadow-sm">
              <p className="mb-3 text-sm font-bold text-ink">
                Top câu hỏi ({metrics.hours}h)
              </p>
              <div className="divide-y divide-line">
                {metrics.top_queries.map((q, i) => (
                  <div key={i} className="flex items-center gap-3 py-2">
                    <span className="w-6 text-center text-xs font-bold text-ink-soft/40">
                      {i + 1}
                    </span>
                    <span className="flex-1 truncate text-sm text-ink">
                      {q.query}
                    </span>
                    <span className="text-xs font-semibold text-teal">
                      {q.count}×
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}
