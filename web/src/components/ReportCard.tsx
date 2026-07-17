"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import {
  Copy,
  Download,
  FileText,
  LayoutDashboard,
  Newspaper,
  ThumbsDown,
  ThumbsUp,
  TriangleAlert,
} from "lucide-react";
import {
  postArticle,
  postFeedback,
  reviseArticle,
  saveDashboard,
  exportWord,
} from "@/lib/api";
import type { ChartType, ChatResponse } from "@/lib/types";
import { downloadCsv, downloadText, friendlyLabel } from "@/lib/format";
import { compatibleCharts } from "@/lib/viz";
import { useChatStore } from "@/store/chat-store";
import { cn } from "@/lib/utils";
import { InsightBlock } from "@/components/InsightBlock";
import { KpiRow } from "@/components/KpiRow";
import { ReportDataView } from "@/components/ReportDataView";
import { ArticlePanel } from "@/components/ArticlePanel";

const CHART_OPTIONS: { value: ChartType; label: string }[] = [
  { value: "bar", label: "Cột" },
  { value: "line", label: "Đường" },
  { value: "area", label: "Miền" },
  { value: "pie", label: "Tròn" },
  { value: "combo", label: "Combo" },
  { value: "candlestick", label: "Nến" },
  { value: "heatmap", label: "Nhiệt" },
  { value: "scatter", label: "Phân tán" },
  { value: "treemap", label: "Cây" },
  { value: "radar", label: "Radar" },
  { value: "waterfall", label: "Thác nước" },
  { value: "table", label: "Bảng" },
];

function confidenceBadge(source: string | null | undefined): {
  label: string;
  className: string;
} | null {
  if (!source) return null;
  if (source === "fast_path" || source === "fast_path_fallback") {
    return { label: "Tin cậy cao", className: "bg-teal/10 text-teal" };
  }
  if (source === "few_shot_retrieval") {
    return {
      label: "Mẫu chuẩn (few-shot)",
      className: "bg-teal/10 text-teal",
    };
  }
  if (source === "cache") {
    return { label: "Từ cache", className: "bg-mist text-ink-soft" };
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
  const [chartReady, setChartReady] = useState(
    (payload.chart_type || "bar") === "table",
  );
  const [writing, setWriting] = useState(false);
  const [writingLabel, setWritingLabel] = useState("Đang viết bài…");
  const [exporting, setExporting] = useState(false);
  const [savingDash, setSavingDash] = useState(false);
  const [sendingVote, setSendingVote] = useState(false);
  const [copied, setCopied] = useState(false);
  const [dashUrl, setDashUrl] = useState<string | null>(null);
  const getPngRef = useRef<(() => string | null) | null>(null);

  const labels = useMemo(
    () => payload.column_labels || {},
    [payload.column_labels],
  );
  const hasData =
    (payload.data?.length || 0) > 0 && payload.status === "success";
  const confidence = confidenceBadge(payload.sql_source);
  const voted = msg?.feedback ?? null;
  const allowedCharts = useMemo(
    () =>
      hasData
        ? new Set(compatibleCharts(payload.data))
        : new Set<ChartType>(["table"]),
    [hasData, payload.data],
  );

  // Viz-only: ưu tiên insight đã gắn từ backend (previous_insight);
  // fallback tìm báo cáo gốc nếu vẫn chỉ là câu ngắn.
  const resolvedInsight = useMemo(() => {
    if (payload.viz_only) {
      const text = (payload.insight || "").trim();
      const isShortSwitch =
        !text ||
        (/^Đã chuyển hiển thị/i.test(text) && text.length < 160);
      if (text && !isShortSwitch) return text;
      for (let i = messages.length - 1; i >= 0; i--) {
        const m = messages[i];
        if (
          m.id !== messageId &&
          m.role === "assistant" &&
          m.payload?.insight &&
          !m.payload.viz_only
        ) {
          return m.payload.insight;
        }
      }
      return text;
    }
    return payload.insight || "";
  }, [payload.insight, payload.viz_only, messages, messageId]);

  const renamed = useMemo(() => {
    return (payload.data || []).map((row) => {
      const out: Record<string, unknown> = {};
      for (const [k, v] of Object.entries(row)) {
        out[friendlyLabel(k, labels)] = v;
      }
      return out;
    });
  }, [payload.data, labels]);

  const onChartReady = useCallback((getPng: () => string | null) => {
    getPngRef.current = getPng;
    setChartReady(true);
  }, []);

  async function onChartChange(next: ChartType) {
    setChartType(next);
    if (next !== "table") {
      setChartReady(false);
      getPngRef.current = null;
    } else {
      setChartReady(true);
    }
    updateMessage(messageId, {
      payload: { ...payload, chart_type: next },
    });
  }

  async function copySql() {
    try {
      await navigator.clipboard.writeText(payload.sql_query);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  }

  async function writeArticle() {
    if (!payload.data?.length) return;
    setWriting(true);
    setWritingLabel("Đang chuẩn bị…");
    try {
      const chartImage = getPngRef.current?.() || null;
      const article = await postArticle({
        domainId,
        question: payload.query,
        data: payload.data,
        insightSummary: resolvedInsight,
        onProgress: (step) => setWritingLabel(step),
      });
      // Ghép ảnh chart phía client — không gửi API
      if (!article.error && chartImage) {
        article.chart_preview_base64 = chartImage;
      }
      updateMessage(messageId, { article });
    } catch (err) {
      updateMessage(messageId, {
        article: {
          article_markdown: "",
          outline: {},
          word_count: 0,
          domain_id: domainId,
          question: payload.query,
          error:
            err instanceof Error
              ? err.message
              : "Lỗi mạng khi gọi API viết bài",
        },
      });
    } finally {
      setWriting(false);
      setWritingLabel("Đang viết bài…");
    }
  }

  async function reviseCurrentArticle(instruction: string): Promise<string | null> {
    const current = msg?.article;
    if (!current?.article_markdown) return "Chưa có bài viết để sửa.";
    const revised = await reviseArticle({
      domainId,
      question: payload.query,
      articleMarkdown: current.article_markdown,
      instruction,
      insightSummary: resolvedInsight,
    });
    if (revised.error) return revised.error;
    updateMessage(messageId, {
      article: {
        ...current,
        ...revised,
        chart_preview_base64:
          current.chart_preview_base64 || revised.chart_preview_base64 || null,
      },
    });
    return null;
  }

  async function downloadWord() {
    if (!payload.data?.length) return;
    if (chartType !== "table" && !chartReady) return;
    setExporting(true);
    try {
      const chartImage = getPngRef.current?.() || undefined;
      await exportWord({
        domainId,
        query: payload.query,
        insight: resolvedInsight,
        data: payload.data,
        articleMarkdown: msg?.article?.article_markdown,
        chartImageBase64: chartImage,
      });
    } catch (err) {
      alert(
        `Không thể xuất Word: ${err instanceof Error ? err.message : "Lỗi không rõ"}`,
      );
    } finally {
      setExporting(false);
    }
  }

  async function pinDashboard() {
    setSavingDash(true);
    try {
      const chartImage = getPngRef.current?.() || undefined;
      const res = await saveDashboard({
        title: payload.query.slice(0, 80),
        domainId,
        reports: [
          {
            query: payload.query,
            insight: resolvedInsight || payload.insight,
            data: payload.data,
            chart_type: chartType,
            column_labels: labels,
            chart_image_base64: chartImage,
            article_markdown: msg?.article?.article_markdown,
            period_comparison: payload.period_comparison,
            forecast: payload.forecast,
          },
        ],
      });
      if (res.id) setDashUrl(`/dashboard/${res.id}`);
    } finally {
      setSavingDash(false);
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
            {payload.chart_template?.name && (
              <span className="rounded-md bg-teal/10 px-2 py-0.5 text-teal">
                Mẫu: {payload.chart_template.name}
              </span>
            )}
            {payload.trust_meta?.price_sources &&
              payload.trust_meta.price_sources.length > 0 && (
                <span className="rounded-md bg-mist px-2 py-0.5">
                  Nguồn: {payload.trust_meta.price_sources.join(", ")}
                </span>
              )}
          </div>
        </div>

        {hasData && (
          <div className="flex flex-col items-end gap-1">
            <label className="flex items-center gap-2 text-xs text-ink-soft">
              Biểu đồ
              <select
                value={chartType}
                onChange={(e) =>
                  void onChartChange(e.target.value as ChartType)
                }
                className="rounded-lg border border-line bg-foam px-2 py-1.5 text-sm text-ink outline-none focus:border-teal"
              >
                {CHART_OPTIONS.map((o) => {
                  const ok =
                    o.value === "table" ||
                    o.value === chartType ||
                    allowedCharts.has(o.value);
                  return (
                    <option key={o.value} value={o.value} disabled={!ok}>
                      {o.label}
                      {!ok ? " (không phù hợp data)" : ""}
                    </option>
                  );
                })}
              </select>
            </label>
          </div>
        )}
      </div>

      <div className="space-y-5 p-5">
        {(resolvedInsight || payload.insight) && (
          <InsightBlock text={resolvedInsight || payload.insight} />
        )}

        {hasData && (
          <KpiRow
            data={payload.data}
            labels={labels}
            period={payload.period_comparison}
            forecast={payload.forecast}
          />
        )}

        {hasData && (
          <ReportDataView
            data={payload.data}
            chartType={chartType}
            labels={labels}
            forecast={payload.forecast}
            query={payload.query}
            dataAsOf={payload.data_as_of}
            chartTemplate={payload.chart_template}
            shapeNotes={payload.shape_notes}
            trustMeta={payload.trust_meta}
            onChartReady={onChartReady}
            onChartChange={(t) => void onChartChange(t)}
          />
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
            <div className="mt-2 flex items-start justify-between gap-2">
              <pre className="flex-1 overflow-x-auto text-xs leading-relaxed text-ink-soft">
                {payload.sql_query}
              </pre>
              <button
                type="button"
                onClick={() => void copySql()}
                className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 text-[11px] font-semibold text-ink-soft hover:text-ink"
              >
                <Copy className="h-3 w-3" />
                {copied ? "Đã copy" : "Copy"}
              </button>
            </div>
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
              disabled={exporting || (chartType !== "table" && !chartReady)}
              onClick={() => void downloadWord()}
              title={
                chartType !== "table" && !chartReady
                  ? "Đang chuẩn bị biểu đồ…"
                  : undefined
              }
              className="inline-flex items-center gap-2 rounded-xl border border-line bg-foam px-3 py-2 text-sm font-semibold text-ink-soft transition hover:border-teal/30 hover:text-ink disabled:opacity-50"
            >
              <FileText className="h-4 w-4" />
              {exporting
                ? "Word…"
                : chartType !== "table" && !chartReady
                  ? "Word…"
                  : "Word"}
            </button>
            <button
              type="button"
              disabled={writing}
              onClick={() => void writeArticle()}
              className="inline-flex items-center gap-2 rounded-xl bg-ink px-3 py-2 text-sm font-semibold text-foam transition hover:bg-ink-soft disabled:opacity-50"
            >
              <Newspaper className="h-4 w-4" />
              {writing ? writingLabel : "Viết bài báo"}
            </button>
            <button
              type="button"
              disabled={savingDash}
              onClick={() => void pinDashboard()}
              className="inline-flex items-center gap-2 rounded-xl border border-teal/30 bg-teal/10 px-3 py-2 text-sm font-semibold text-teal transition hover:bg-teal/15 disabled:opacity-50"
            >
              <LayoutDashboard className="h-4 w-4" />
              {savingDash ? "Đang lưu…" : "Lưu dashboard"}
            </button>
            {dashUrl && (
              <a
                href={dashUrl}
                target="_blank"
                rel="noreferrer"
                className="text-xs font-semibold text-teal underline"
              >
                Mở dashboard
              </a>
            )}

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
            onRevise={reviseCurrentArticle}
          />
        )}
      </div>
    </section>
  );
}
