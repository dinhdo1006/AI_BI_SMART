"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Download, X } from "lucide-react";
import type { ArticleResponse } from "@/lib/types";
import { downloadText } from "@/lib/format";

export function ArticlePanel({
  article,
  onClear,
}: {
  article: ArticleResponse;
  onClear: () => void;
}) {
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
