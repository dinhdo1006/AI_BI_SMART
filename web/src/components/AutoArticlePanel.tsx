"use client";

import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, FileText, Play, RefreshCw, X } from "lucide-react";
import {
  exportWord,
  fetchAutoArticleScheduler,
  fetchAutoArticles,
  runAutoArticleChecks,
  runAutoArticleJob,
} from "@/lib/api";
import { downloadText } from "@/lib/format";
import type { AutoArticle, AutoArticleSchedulerStatus } from "@/lib/types";
import { cn } from "@/lib/utils";

function slugFilename(article: AutoArticle, ext: string): string {
  const base = `${article.template_id || "bai"}-${article.data_date || "ky"}`
    .replace(/[^\w.-]+/g, "-")
    .replace(/-+/g, "-");
  return `${base}.${ext}`;
}

export function AutoArticlePanel({ domainId }: { domainId: string }) {
  const [open, setOpen] = useState(false);
  const [articles, setArticles] = useState<AutoArticle[]>([]);
  const [scheduler, setScheduler] =
    useState<AutoArticleSchedulerStatus | null>(null);
  const [selected, setSelected] = useState<AutoArticle | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setError(null);
    try {
      const [list, sched] = await Promise.all([
        fetchAutoArticles(domainId, 20),
        fetchAutoArticleScheduler(),
      ]);
      setArticles(list);
      setScheduler(sched);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Không tải được bài auto");
    }
  }, [domainId]);

  useEffect(() => {
    if (!open) return;
    void reload();
    const t = setInterval(() => void reload(), 60_000);
    return () => clearInterval(t);
  }, [open, reload]);

  async function onRunChecks() {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const result = await runAutoArticleChecks();
      setNote(
        `Đã kiểm tra ${result.checked} job · ok ${result.ok_count} · skip ${result.skipped_count} · lỗi ${result.error_count}`,
      );
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Chạy checks thất bại");
    } finally {
      setBusy(false);
    }
  }

  async function onForceDaily() {
    setBusy(true);
    setError(null);
    setNote(null);
    try {
      const today = new Date().toISOString().slice(0, 10);
      const result = await runAutoArticleJob({
        templateId: "market_01",
        dataDate: today,
        domainId,
        force: true,
      });
      setNote(
        result.status === "ok"
          ? `Đã viết bài ${result.article?.template_name || "market_01"}`
          : result.message || result.status,
      );
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Viết bài thất bại");
    } finally {
      setBusy(false);
    }
  }

  function downloadMarkdown(article: AutoArticle) {
    downloadText(
      article.article_markdown,
      slugFilename(article, "md"),
      "text/markdown;charset=utf-8",
    );
  }

  async function downloadWord(article: AutoArticle) {
    setExporting(true);
    setError(null);
    try {
      await exportWord({
        domainId: article.domain_id || domainId,
        query: article.question,
        insight: "",
        data: [],
        articleMarkdown: article.article_markdown,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Xuất Word thất bại");
    } finally {
      setExporting(false);
    }
  }

  return (
    <div className="rounded-xl border border-line bg-white/70">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
          <FileText className="h-3.5 w-3.5 text-teal" />
          Bài tự động ({articles.length || "—"})
        </span>
        <span className="text-[10px] text-ink-soft/55">
          {open ? "Thu gọn" : "Mở"}
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-line px-3 py-3">
          {scheduler && (
            <p className="text-[11px] leading-snug text-ink-soft/75">
              {scheduler.enabled && scheduler.running
                ? `Scheduler mỗi ${scheduler.interval_minutes} phút · daily ${scheduler.daily_time}${
                    scheduler.intraday_enabled !== false
                      ? " · theo dõi cập nhật trong ngày"
                      : ""
                  }`
                : "Scheduler tắt — chỉ chạy tay"}
              {scheduler.last_run_at
                ? ` · gần nhất ${new Date(scheduler.last_run_at).toLocaleTimeString("vi-VN")}`
                : ""}
              {scheduler.last_error ? ` · lỗi: ${scheduler.last_error}` : ""}
            </p>
          )}

          <div className="flex flex-wrap gap-1.5">
            <button
              type="button"
              disabled={busy}
              onClick={() => void reload()}
              className="inline-flex items-center gap-1 rounded-lg border border-line bg-foam px-2 py-1 text-[11px] font-semibold text-ink-soft hover:text-ink disabled:opacity-50"
            >
              <RefreshCw className={cn("h-3 w-3", busy && "animate-spin")} />
              Tải lại
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onRunChecks()}
              className="inline-flex items-center gap-1 rounded-lg border border-teal/30 bg-teal/10 px-2 py-1 text-[11px] font-semibold text-teal disabled:opacity-50"
            >
              <Play className="h-3 w-3" />
              Chạy checks
            </button>
            <button
              type="button"
              disabled={busy}
              onClick={() => void onForceDaily()}
              className="inline-flex items-center gap-1 rounded-lg border border-line bg-white px-2 py-1 text-[11px] font-semibold text-ink-soft hover:text-ink disabled:opacity-50"
            >
              Viết daily (force)
            </button>
          </div>

          {note && (
            <p className="rounded-lg bg-teal/5 px-2 py-1.5 text-[11px] text-teal">
              {note}
            </p>
          )}
          {error && (
            <p className="rounded-lg bg-copper-soft/40 px-2 py-1.5 text-[11px] text-ink-soft">
              {error}
            </p>
          )}

          <ul className="max-h-56 space-y-1.5 overflow-y-auto scrollbar-thin">
            {articles.length === 0 && (
              <li className="text-[12px] text-ink-soft/60">
                Chưa có bài tự động. Bật ARTICLE_SCHEDULE_ENABLED hoặc bấm
                “Chạy checks”.
              </li>
            )}
            {articles.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  onClick={() => setSelected(a)}
                  className="w-full rounded-lg border border-line bg-foam/60 px-2 py-1.5 text-left hover:border-teal/40"
                >
                  <p className="text-[12px] font-semibold text-ink">
                    {a.template_name}
                  </p>
                  <p className="mt-0.5 text-[10px] text-ink-soft/65">
                    {a.data_date} · {a.trigger} · {a.word_count} từ
                    {a.generated_at ? ` · ${a.generated_at}` : ""}
                  </p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink/40 p-4">
          <div className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-line bg-white shadow-xl">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
              <div className="min-w-0 flex-1">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-teal">
                  {selected.template_name}
                </p>
                <p className="text-sm font-semibold text-ink">
                  {selected.question}
                </p>
                <p className="mt-0.5 text-[11px] text-ink-soft">
                  Thời gian tạo báo cáo: {selected.generated_at} · kỳ{" "}
                  {selected.data_date}
                </p>
                <p className="mt-1 text-[10px] text-ink-soft/60">
                  Đã lưu trên server. Tải về máy bằng Markdown hoặc Word.
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                <button
                  type="button"
                  onClick={() => downloadMarkdown(selected)}
                  className="inline-flex items-center gap-1 rounded-lg border border-line bg-foam px-2.5 py-1.5 text-xs font-semibold text-ink-soft hover:text-ink"
                >
                  <Download className="h-3.5 w-3.5" />
                  Markdown
                </button>
                <button
                  type="button"
                  disabled={exporting}
                  onClick={() => void downloadWord(selected)}
                  className="inline-flex items-center gap-1 rounded-lg border border-teal/30 bg-teal/10 px-2.5 py-1.5 text-xs font-semibold text-teal disabled:opacity-50"
                >
                  <Download className="h-3.5 w-3.5" />
                  {exporting ? "Đang xuất…" : "Word"}
                </button>
                <button
                  type="button"
                  onClick={() => setSelected(null)}
                  className="rounded-lg border border-line p-1.5 text-ink-soft hover:text-ink"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="prose-article overflow-y-auto px-6 py-5 scrollbar-thin">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {selected.article_markdown}
              </ReactMarkdown>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
