"use client";

import { useMemo, useState } from "react";
import {
  Download,
  FileText,
  Newspaper,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
} from "lucide-react";
import { postArticle, postFeedback } from "@/lib/api";
import type { ChartType, ChatResponse } from "@/lib/types";
import { downloadCsv, downloadText, friendlyLabel } from "@/lib/format";
import { useChatStore } from "@/store/chat-store";
import { cn } from "@/lib/utils";
import { InsightBlock } from "@/components/InsightBlock";
import { KpiRow } from "@/components/KpiRow";
import { DataChart } from "@/components/DataChart";
import { DataTable } from "@/components/DataTable";
import { ArticlePanel } from "@/components/ArticlePanel";

const CHART_OPTIONS: { value: ChartType; label: string }[] = [
  { value: "bar", label: "Cột" },
  { value: "line", label: "Đường" },
  { value: "area", label: "Miền" },
  { value: "pie", label: "Tròn" },
  { value: "combo", label: "Combo" },
  { value: "table", label: "Bảng" },
];

/** Badge tin cậy từ sql_source — chỉ hiện khi có SQL thật. */
function confidenceBadge(source: string | null | undefined): {
  label: string;
  className: string;
} | null {
  if (!source) return null;
  if (source === "fast_path" || source === "fast_path_fallback") {
    return {
      label: "Tin cậy cao",
      className: "bg-teal/10 text-teal",
    };
  }
  if (source === "llm" || source === "llm_followup") {
    return {
      label: "Ước tính — kiểm tra SQL",
      className: "bg-copper-soft/70 text-copper",
    };
  }
  if (source === "repair") {
    return {
      label: "Đã sửa — cần xác minh",
      className: "bg-copper-soft text-copper font-semibold",
    };
  }
  return null;
}

function formatDataAsOf(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (!m) return iso;
  return `${m[3]}/${m[2]}/${m[1]}`;
}

export function ReportCard({
  payload,
  reportIndex,
  messageId,
}: {
  payload: ChatResponse;
  reportIndex: number;
  messageId: string;
}) {
  const domainId = useChatStore((s) => s.domainId);
  const updateMessage = useChatStore((s) => s.updateMessage);
  const messages = useChatStore((s) => s.messages);
  const msg = messages.find((m) => m.id === messageId);

  const [chartType, setChartType] = useState<ChartType>(
    payload.chart_type || "bar",
  );
  const [writing, setWriting] = useState(false);
  const [sendingVote, setSendingVote] = useState(false);

  const labels = payload.column_labels || {};
  const hasData = (payload.data?.length || 0) > 0 && payload.status === "success";
  const confidence = confidenceBadge(payload.sql_source);
  const voted = msg?.feedback ?? null;
  const renamed = useMemo(() => {
    return (payload.data || []).map((row) => {
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(row)) {
        out[friendlyLabel(k, labels)] = v;
      }
      return out;
    });
  }, [payload.data, labels]);

  async function onChartChange(next: ChartType) {
    // Đổi loại chart ngay trên client — không gọi API (tránh backend ghi đè)
    setChartType(next);
    updateMessage(messageId, {
      payload: { ...payload, chart_type: next },
    });
  }

  async function writeArticle() {
    if (!payload.data?.length) return;
    setWriting(true);
    try {
      const article = await postArticle({
        domainId,
        question: payload.query,
        data: payload.data,
        insightSummary: payload.insight || "",
      });
      updateMessage(messageId, { article });
    } finally {
      setWriting(false);
    }
  }

  async function sendVote(vote: "up" | "down") {
    if (voted || sendingVote) return;
    setSendingVote(true);
    const ok = await postFeedback({
      domainId,
      query: payload.query,
      vote,
      sqlQuery: payload.sql_query,
      sqlSource: payload.sql_source,
      status: payload.status,
    });
    setSendingVote(false);
    if (ok) updateMessage(messageId, { feedback: vote });
  }

  if (payload.status === "error" || payload.error) {
    return (
      <section className="w-full max-w-4xl rounded-2xl border border-copper/25 bg-copper-soft/40 p-5">
        <div className="flex items-start gap-3">
          <TriangleAlert className="mt-0.5 h-5 w-5 shrink-0 text-copper" />
          <div>
            <h3 className="font-[family-name:var(--font-display)] text-lg font-bold text-ink">
              Lỗi truy vấn
            </h3>
            <p className="mt-1 text-sm text-ink-soft">
              {payload.error || payload.error_detail || "Không rõ nguyên nhân."}
            </p>
            {payload.failed_sql && (
              <pre className="mt-3 overflow-x-auto rounded-xl bg-ink/90 p-3 text-xs text-foam/90">
                {payload.failed_sql}
              </pre>
            )}
          </div>
        </div>
      </section>
    );
  }

  return (
    <section className="w-full overflow-hidden rounded-2xl border border-line bg-white/95 shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-teal">
            Báo cáo #{reportIndex}
          </p>
          <h3 className="mt-0.5 font-[family-name:var(--font-display)] text-lg font-bold text-ink">
            {payload.query}
          </h3>
          <div className="mt-1.5 flex flex-wrap gap-2 text-[11px] text-ink-soft/70">
            {confidence && (
              <span
                className={cn(
                  "rounded-md px-2 py-0.5 font-medium",
                  confidence.className,
                )}
              >
                {confidence.label}
              </span>
            )}
            {payload.from_cache && (
              <span className="rounded-md bg-mist px-2 py-0.5">cache</span>
            )}
            {payload.viz_only && (
              <span className="rounded-md bg-mist px-2 py-0.5">viz only</span>
            )}
            <span className="rounded-md bg-mist px-2 py-0.5">
              {payload.row_count} dòng
            </span>
            {payload.data_as_of && (
              <span className="rounded-md bg-mist px-2 py-0.5">
                Dữ liệu tới {formatDataAsOf(payload.data_as_of)}
              </span>
            )}
          </div>
        </div>

        {hasData && (
          <div className="flex flex-wrap items-center gap-2">
            <label className="flex items-center gap-2 text-xs text-ink-soft">
              Biểu đồ
              <select
                value={chartType}
                onChange={(e) => void onChartChange(e.target.value as ChartType)}
                className="rounded-lg border border-line bg-foam px-2 py-1.5 text-sm text-ink outline-none focus:border-teal"
              >
                {CHART_OPTIONS.map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
      </div>

      <div className="space-y-5 p-5">
        {payload.insight && <InsightBlock text={payload.insight} />}

        {hasData && <KpiRow data={payload.data} labels={labels} />}

        {hasData && (
          <div
            className={cn(
              "grid gap-4",
              chartType === "table"
                ? "grid-cols-1"
                : "grid-cols-1 xl:grid-cols-[0.95fr_1.15fr]",
            )}
          >
            <DataTable data={renamed} />
            {chartType !== "table" && (
              <DataChart
                data={payload.data}
                chartType={chartType}
                labels={labels}
              />
            )}
          </div>
        )}

        {payload.status === "empty" && (
          <p className="rounded-xl bg-mist/80 px-4 py-3 text-sm text-ink-soft">
            Không có dòng dữ liệu nào khớp yêu cầu.
          </p>
        )}

        {payload.sql_query && !payload.sql_query.startsWith("(") && (
          <details className="rounded-xl border border-line bg-foam/60 px-4 py-3">
            <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
              SQL đã chạy
            </summary>
            <pre className="mt-2 overflow-x-auto text-xs leading-relaxed text-ink-soft">
              {payload.sql_query}
            </pre>
          </details>
        )}

        {hasData && (
          <div className="flex flex-wrap items-center gap-2 border-t border-line pt-4">
            <button
              type="button"
              onClick={() => downloadCsv(renamed)}
              className="inline-flex items-center gap-2 rounded-xl border border-line bg-foam px-3 py-2 text-sm font-semibold text-ink-soft transition hover:border-teal/30 hover:text-ink"
            >
              <Download className="h-4 w-4" />
              CSV
            </button>
            <button
              type="button"
              onClick={() =>
                downloadText(
                  JSON.stringify(payload.data, null, 2),
                  "bi_export.json",
                  "application/json",
                )
              }
              className="inline-flex items-center gap-2 rounded-xl border border-line bg-foam px-3 py-2 text-sm font-semibold text-ink-soft transition hover:border-teal/30 hover:text-ink"
            >
              <FileText className="h-4 w-4" />
              JSON
            </button>
            <button
              type="button"
              disabled={writing}
              onClick={() => void writeArticle()}
              className="inline-flex items-center gap-2 rounded-xl bg-ink px-3 py-2 text-sm font-semibold text-foam transition hover:bg-ink-soft disabled:opacity-50"
            >
              <Newspaper className="h-4 w-4" />
              {writing ? "Đang viết…" : "Viết bài báo"}
            </button>

            <div className="ml-auto flex items-center gap-1.5">
              <span className="mr-1 text-[11px] text-ink-soft/60">
                {voted ? "Đã ghi nhận" : "Hữu ích?"}
              </span>
              <button
                type="button"
                disabled={!!voted || sendingVote}
                onClick={() => void sendVote("up")}
                aria-label="Hữu ích"
                className={cn(
                  "inline-flex h-9 w-9 items-center justify-center rounded-xl border transition disabled:opacity-50",
                  voted === "up"
                    ? "border-teal/40 bg-teal/10 text-teal"
                    : "border-line bg-foam text-ink-soft hover:border-teal/30 hover:text-ink",
                )}
              >
                <ThumbsUp className="h-4 w-4" />
              </button>
              <button
                type="button"
                disabled={!!voted || sendingVote}
                onClick={() => void sendVote("down")}
                aria-label="Không hữu ích"
                className={cn(
                  "inline-flex h-9 w-9 items-center justify-center rounded-xl border transition disabled:opacity-50",
                  voted === "down"
                    ? "border-copper/40 bg-copper-soft text-copper"
                    : "border-line bg-foam text-ink-soft hover:border-copper/30 hover:text-ink",
                )}
              >
                <ThumbsDown className="h-4 w-4" />
              </button>
            </div>
          </div>
        )}

        {msg?.article && (
          <ArticlePanel
            article={msg.article}
            onClear={() => updateMessage(messageId, { article: null })}
          />
        )}
      </div>
    </section>
  );
}
