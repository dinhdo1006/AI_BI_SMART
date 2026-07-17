"use client";

import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, Loader2, Sparkles, X } from "lucide-react";
import type { ArticleResponse } from "@/lib/types";
import { downloadText } from "@/lib/format";

export function ArticlePanel({
  article,
  onClear,
  onRevise,
}: {
  article: ArticleResponse;
  onClear: () => void;
  onRevise?: (instruction: string) => Promise<string | null>;
}) {
  const [instruction, setInstruction] = useState("");
  const [revising, setRevising] = useState(false);
  const [reviseError, setReviseError] = useState<string | null>(null);

  if (article.error) {
    return (
      <div className="rounded-xl border border-copper/30 bg-copper-soft/50 px-4 py-3 text-sm text-ink-soft">
        Không viết được bài: {article.error}
      </div>
    );
  }

  const chartSrc = article.chart_preview_base64
    ? article.chart_preview_base64.startsWith("data:")
      ? article.chart_preview_base64
      : `data:image/png;base64,${article.chart_preview_base64}`
    : null;

  async function submitRevision() {
    const ask = instruction.trim();
    if (!ask || !onRevise || revising) return;
    setRevising(true);
    setReviseError(null);
    try {
      const error = await onRevise(ask);
      if (error) {
        setReviseError(error);
        return;
      }
      setInstruction("");
    } catch (err) {
      setReviseError(
        err instanceof Error ? err.message : "Không sửa được bài viết",
      );
    } finally {
      setRevising(false);
    }
  }

  return (
    <div className="overflow-hidden rounded-xl border border-line bg-foam/50">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-teal">
            Narrative Planner
          </p>
          <p className="font-[family-name:var(--font-serif)] text-lg font-semibold text-ink">
            Bài phân tích · {article.word_count} từ
          </p>
          {(article.template_name || article.generated_at) && (
            <p className="mt-0.5 text-xs text-ink-soft">
              {article.template_name
                ? `Template: ${article.template_name}`
                : null}
              {article.template_name && article.generated_at ? " · " : null}
              {article.generated_at
                ? `Thời gian tạo báo cáo: ${article.generated_at}`
                : null}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() =>
              downloadText(
                article.article_markdown,
                "bai-phan-tich.md",
                "text/markdown;charset=utf-8",
              )
            }
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-ink-soft hover:text-ink"
          >
            <Download className="h-3.5 w-3.5" />
            Markdown
          </button>
          <button
            type="button"
            onClick={onClear}
            className="inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-ink-soft hover:text-copper"
          >
            <X className="h-3.5 w-3.5" />
            Đóng
          </button>
        </div>
      </div>
      {onRevise && (
        <div className="border-b border-line bg-white/70 px-4 py-3">
          <label className="mb-1.5 block text-xs font-semibold text-ink">
            Yêu cầu AI sửa bài
          </label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <textarea
              value={instruction}
              onChange={(e) => setInstruction(e.target.value)}
              disabled={revising}
              rows={2}
              placeholder="Ví dụ: Viết ngắn hơn, thêm mục rủi ro, đổi giọng văn chuyên nghiệp hơn..."
              className="min-h-16 flex-1 rounded-xl border border-line bg-white px-3 py-2 text-sm text-ink outline-none transition placeholder:text-ink-soft/45 focus:border-teal/40 focus:ring-2 focus:ring-teal/10 disabled:opacity-60"
            />
            <button
              type="button"
              onClick={() => void submitRevision()}
              disabled={revising || !instruction.trim()}
              className="inline-flex items-center justify-center gap-1.5 rounded-xl bg-teal px-3 py-2 text-sm font-semibold text-white transition hover:bg-teal/90 disabled:cursor-not-allowed disabled:opacity-50 sm:w-32"
            >
              {revising ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {revising ? "Đang sửa" : "AI sửa bài"}
            </button>
          </div>
          {reviseError && (
            <p className="mt-2 text-xs font-medium text-copper">
              {reviseError}
            </p>
          )}
        </div>
      )}
      <div className="prose-article max-h-[560px] overflow-y-auto px-5 py-4 scrollbar-thin">
        {chartSrc && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={chartSrc}
            alt="Biểu đồ phân tích"
            className="mb-5 max-h-[320px] w-full rounded-xl border border-line object-contain bg-white"
          />
        )}
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            img: ({ src, alt }) =>
              src ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={src}
                  alt={alt || "Biểu đồ"}
                  className="my-4 max-h-[360px] w-full rounded-xl border border-line object-contain bg-white"
                />
              ) : null,
          }}
        >
          {article.article_markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
