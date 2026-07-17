"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Bell, Play, Plus, Trash2 } from "lucide-react";
import {
  createAlertRule,
  deleteAlertRule,
  fetchAlertEvents,
  fetchAlertMetrics,
  fetchAlertRules,
  fetchAlertScheduler,
  patchAlertRule,
  runAlerts,
} from "@/lib/api";
import type {
  AlertEvent,
  AlertMetric,
  AlertOperator,
  AlertRule,
  AlertSchedulerStatus,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const OPS: { value: AlertOperator; label: string }[] = [
  { value: "gt", label: ">" },
  { value: "gte", label: "≥" },
  { value: "lt", label: "<" },
  { value: "lte", label: "≤" },
  { value: "eq", label: "=" },
];

function applyMetricDefaults(
  m: AlertMetric,
  setters: {
    setTarget: (v: string) => void;
    setName: (fn: (prev: string) => string) => void;
    setOperator: (op: AlertOperator) => void;
    setThreshold: (v: string) => void;
  },
) {
  setters.setTarget(m.target_placeholder || "");
  setters.setName((prev) =>
    prev.startsWith("Alert ") || !prev ? `Alert ${m.label}` : prev,
  );
  if (m.default_operator) setters.setOperator(m.default_operator);
  if (m.default_threshold != null) {
    setters.setThreshold(String(m.default_threshold));
  } else if (m.kind === "anomaly") {
    setters.setThreshold("2.5");
  }
}

export function AlertPanel({ domainId }: { domainId: string }) {
  const [open, setOpen] = useState(false);
  const [metrics, setMetrics] = useState<AlertMetric[]>([]);
  const [rules, setRules] = useState<AlertRule[]>([]);
  const [events, setEvents] = useState<AlertEvent[]>([]);
  const [scheduler, setScheduler] = useState<AlertSchedulerStatus | null>(
    null,
  );
  const [busy, setBusy] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runNote, setRunNote] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [metricKey, setMetricKey] = useState("");
  const [operator, setOperator] = useState<AlertOperator>("gt");
  const [threshold, setThreshold] = useState("20");
  const [target, setTarget] = useState("");

  const selectedMetric = useMemo(
    () => metrics.find((m) => m.key === metricKey) || null,
    [metrics, metricKey],
  );

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [m, r, e, s] = await Promise.all([
        fetchAlertMetrics(domainId),
        fetchAlertRules(domainId),
        fetchAlertEvents(domainId, 12),
        fetchAlertScheduler(),
      ]);
      setMetrics(m);
      setRules(r);
      setEvents(e);
      setScheduler(s);
      if (m.length && !metricKey) {
        setMetricKey(m[0].key);
        applyMetricDefaults(m[0], {
          setTarget,
          setName,
          setOperator,
          setThreshold,
        });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được alerts");
    }
  }, [domainId, metricKey]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setOpen(false);
      setRunNote(null);
      setMetricKey("");
      setName("");
      setTarget("");
      void reload();
    }, 0);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reload on domain change only
  }, [domainId]);

  async function onCreate() {
    if (!metricKey || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await createAlertRule({
        domainId,
        name: name.trim(),
        metricKey,
        operator,
        threshold: Number(threshold),
        target: selectedMetric?.needs_target ? target.trim() : undefined,
      });
      setRunNote(null);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Tạo rule thất bại");
    } finally {
      setBusy(false);
    }
  }

  async function onRun() {
    setRunning(true);
    setError(null);
    try {
      const result = await runAlerts(domainId);
      setRunNote(
        `Đã kiểm tra ${result.checked} rule · ${result.triggered_count} vượt ngưỡng` +
          (result.new_event_count != null
            ? ` · ${result.new_event_count} event mới`
            : "") +
          (result.error_count ? ` · ${result.error_count} lỗi` : ""),
      );
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chạy alert thất bại");
    } finally {
      setRunning(false);
    }
  }

  const firedCount = rules.filter((r) => r.last_triggered).length;

  return (
    <div className="rounded-xl border border-line bg-white/70">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
          <Bell className="h-3.5 w-3.5 text-copper" />
          Cảnh báo
          {firedCount > 0 && (
            <span className="rounded-md bg-copper/15 px-1.5 py-0.5 text-[10px] font-bold text-copper">
              {firedCount}
            </span>
          )}
        </span>
        <span className="text-[10px] text-ink-soft/50">
          {open ? "Thu gọn" : "Mở"}
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-line px-3 py-3">
          {scheduler && (
            <p className="rounded-lg bg-mist/70 px-2 py-1.5 text-[11px] text-ink-soft">
              {scheduler.enabled && scheduler.running
                ? `Tự chạy mỗi ${scheduler.interval_minutes} phút`
                : "Scheduler tắt — chỉ kiểm tra tay"}
              {scheduler.last_run_at
                ? ` · lần gần nhất ${new Date(scheduler.last_run_at).toLocaleTimeString("vi-VN")}`
                : ""}
              {scheduler.last_error
                ? ` · lỗi: ${scheduler.last_error}`
                : ""}
            </p>
          )}

          {error && (
            <p className="rounded-lg bg-copper-soft/50 px-2 py-1.5 text-[11px] text-copper">
              {error}
            </p>
          )}
          {runNote && (
            <p className="rounded-lg bg-teal/10 px-2 py-1.5 text-[11px] text-teal">
              {runNote}
            </p>
          )}

          <div className="space-y-2 rounded-lg border border-line bg-mist/40 p-2">
            <p className="text-[11px] font-semibold text-ink-soft/70">
              Tạo rule mới
            </p>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Tên rule"
              className="w-full rounded-lg border border-line bg-white px-2 py-1.5 text-[12px] outline-none focus:border-teal"
            />
            <select
              value={metricKey}
              onChange={(e) => {
                const key = e.target.value;
                setMetricKey(key);
                const m = metrics.find((x) => x.key === key);
                if (m) {
                  applyMetricDefaults(m, {
                    setTarget,
                    setName,
                    setOperator,
                    setThreshold,
                  });
                }
              }}
              className="w-full rounded-lg border border-line bg-white px-2 py-1.5 text-[12px] outline-none"
            >
              {metrics.map((m) => (
                <option key={m.key} value={m.key}>
                  {m.kind === "anomaly" ? "⚡ " : ""}
                  {m.label}
                  {m.unit ? ` (${m.unit})` : ""}
                </option>
              ))}
            </select>
            {selectedMetric?.description && (
              <p className="text-[10px] leading-snug text-ink-soft/65">
                {selectedMetric.description}
              </p>
            )}
            {selectedMetric?.needs_target && (
              <input
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder={
                  selectedMetric.target_placeholder ||
                  selectedMetric.target_label
                }
                className="w-full rounded-lg border border-line bg-white px-2 py-1.5 text-[12px] outline-none focus:border-teal"
              />
            )}
            <div className="flex gap-2">
              <select
                value={operator}
                onChange={(e) =>
                  setOperator(e.target.value as AlertOperator)
                }
                className="w-16 rounded-lg border border-line bg-white px-1 py-1.5 text-[12px]"
              >
                {OPS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
              <input
                type="number"
                value={threshold}
                onChange={(e) => setThreshold(e.target.value)}
                className="min-w-0 flex-1 rounded-lg border border-line bg-white px-2 py-1.5 text-[12px] outline-none focus:border-teal"
              />
            </div>
            <button
              type="button"
              disabled={busy || !metrics.length}
              onClick={() => void onCreate()}
              className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-ink-soft px-2 py-1.5 text-[12px] font-semibold text-white transition hover:bg-ink disabled:opacity-50"
            >
              <Plus className="h-3.5 w-3.5" />
              Thêm rule
            </button>
          </div>

          <button
            type="button"
            disabled={running || !rules.length}
            onClick={() => void onRun()}
            className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-teal px-2 py-2 text-[12px] font-semibold text-white transition hover:bg-teal-deep disabled:opacity-50"
          >
            <Play className="h-3.5 w-3.5" />
            {running ? "Đang kiểm tra…" : "Kiểm tra ngay"}
          </button>

          <ul className="max-h-40 space-y-1.5 overflow-y-auto scrollbar-thin">
            {rules.length === 0 && (
              <li className="text-[11px] text-ink-soft/60">
                Chưa có rule — thêm để hệ thống tự giám sát ngưỡng / anomaly.
              </li>
            )}
            {rules.map((r) => (
              <li
                key={r.id}
                className={cn(
                  "rounded-lg border px-2 py-1.5 text-[11px]",
                  r.last_triggered
                    ? "border-copper/35 bg-copper-soft/40"
                    : "border-line bg-white",
                )}
              >
                <div className="flex items-start justify-between gap-1">
                  <div className="min-w-0">
                    <p className="truncate font-semibold text-ink">{r.name}</p>
                    <p className="mt-0.5 text-ink-soft/70">
                      {r.metric_key}
                      {r.target ? ` · ${r.target}` : ""} ·{" "}
                      {OPS.find((o) => o.value === r.operator)?.label ||
                        r.operator}{" "}
                      {r.threshold}
                      {r.last_value != null
                        ? ` · hiện ${r.last_value}`
                        : ""}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-0.5">
                    <button
                      type="button"
                      title={r.enabled ? "Tắt" : "Bật"}
                      onClick={() =>
                        void patchAlertRule(r.id, {
                          enabled: !r.enabled,
                        }).then(reload)
                      }
                      className={cn(
                        "rounded px-1.5 py-0.5 text-[10px] font-bold",
                        r.enabled
                          ? "bg-teal/15 text-teal"
                          : "bg-mist text-ink-soft",
                      )}
                    >
                      {r.enabled ? "ON" : "OFF"}
                    </button>
                    <button
                      type="button"
                      title="Xóa"
                      onClick={() =>
                        void deleteAlertRule(r.id).then(reload)
                      }
                      className="rounded p-1 text-ink-soft hover:text-copper"
                    >
                      <Trash2 className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {events.length > 0 && (
            <div>
              <p className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-soft/55">
                Lịch sử kích hoạt
              </p>
              <ul className="max-h-40 space-y-1 overflow-y-auto scrollbar-thin">
                {events.slice(0, 12).map((ev) => {
                  const askQ =
                    ev.payload?.suggested_query ||
                    (ev.target
                      ? `Phân tích ${ev.target} liên quan ${ev.metric_key} (ngưỡng ${ev.operator} ${ev.threshold})`
                      : `Giải thích alert ${ev.rule_name}: ${ev.message}`);
                  const when = (() => {
                    try {
                      return new Date(ev.triggered_at).toLocaleString("vi-VN", {
                        day: "2-digit",
                        month: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      });
                    } catch {
                      return ev.triggered_at.slice(0, 16);
                    }
                  })();
                  return (
                    <li
                      key={ev.id}
                      className="rounded-md bg-copper-soft/35 px-2 py-1 text-[10px] leading-snug text-copper"
                    >
                      <div className="flex items-start justify-between gap-1">
                        <p className="min-w-0">{ev.message}</p>
                        <span className="shrink-0 font-mono text-[9px] text-ink-soft/50">
                          #{ev.id.slice(0, 6)}
                        </span>
                      </div>
                      <p className="mt-0.5 text-[9px] text-ink-soft/55">{when}</p>
                      <button
                        type="button"
                        className="mt-0.5 font-semibold underline hover:text-ink"
                        onClick={() =>
                          window.dispatchEvent(
                            new CustomEvent("abi:suggest", {
                              detail: { query: askQ, alertEventId: ev.id },
                            }),
                          )
                        }
                      >
                        Hỏi lại trong chat →
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
