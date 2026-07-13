"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, Loader2 } from "lucide-react";
import { postChat } from "@/lib/api";
import type { HistoryMessage } from "@/lib/types";
import { isVizOnlyRequest } from "@/lib/viz";
import { useChatStore } from "@/store/chat-store";
import { EmptyHero } from "./EmptyHero";
import { ReportCard } from "./ReportCard";
import { cn } from "@/lib/utils";

function briefFromPayload(
  status: string,
  fromCache?: boolean,
  vizOnly?: boolean,
) {
  let brief =
    status === "error"
      ? "Không tạo được báo cáo. Xem chi tiết trong khung bên dưới."
      : status === "empty"
        ? "Truy vấn thành công nhưng không có dữ liệu khớp."
        : "Đã tạo báo cáo bên dưới. Có thể tải CSV, đổi biểu đồ hoặc viết bài báo.";
  if (fromCache) brief = `Kết quả lưu — ${brief}`;
  if (vizOnly) brief = `Đổi biểu đồ — ${brief}`;
  return brief;
}

export function ChatPanel() {
  const messages = useChatStore((s) => s.messages);
  const domainId = useChatStore((s) => s.domainId);
  const loading = useChatStore((s) => s.loading);
  const loadingLabel = useChatStore((s) => s.loadingLabel);
  const addUser = useChatStore((s) => s.addUser);
  const addAssistant = useChatStore((s) => s.addAssistant);
  const setLoading = useChatStore((s) => s.setLoading);
  const lastData = useChatStore((s) => s.lastData);

  const [input, setInput] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendQuery(raw: string) {
    const query = raw.trim();
    if (!query || loading) return;

    addUser(query);
    setInput("");

    const history: HistoryMessage[] = useChatStore
      .getState()
      .messages.filter((m) => m.role === "user" || m.content)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    // history includes the just-added user message; API wants prior turns
    const historyForApi = history.slice(0, -1);

    const reuse =
      isVizOnlyRequest(query) && lastData() ? lastData() : null;

    setLoading(
      true,
      reuse
        ? "Đang đổi loại biểu đồ…"
        : "Fast-path / Router / SQLCoder đang xử lý…",
    );

    try {
      const payload = await postChat({
        domainId,
        query,
        history: historyForApi,
        reuseData: reuse,
      });
      payload.query = query;
      payload.domain_id = domainId;
      const brief = briefFromPayload(
        payload.status || (payload.error ? "error" : "success"),
        payload.from_cache,
        payload.viz_only,
      );
      addAssistant(brief, payload);
    } catch (err) {
      addAssistant(
        err instanceof Error ? err.message : "Lỗi không xác định khi gọi API.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const onSuggest = (e: Event) => {
      const q = (e as CustomEvent<string>).detail;
      if (q) void sendQuery(q);
    };
    window.addEventListener("abi:suggest", onSuggest);
    return () => window.removeEventListener("abi:suggest", onSuggest);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domainId, loading]);

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    void sendQuery(input);
  }

  let reportN = 0;

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[22px] border border-line bg-foam/75 shadow-[var(--shadow)] backdrop-blur-md">
      <header className="hidden items-center justify-between border-b border-line px-6 py-4 lg:flex">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-teal">
            Hội thoại & báo cáo
          </p>
          <p className="mt-0.5 font-[family-name:var(--font-display)] text-xl font-bold text-ink">
            Phân tích theo từng câu hỏi
          </p>
        </div>
        <p className="max-w-xs text-right text-xs leading-relaxed text-ink-soft/70">
          Mỗi câu trả lời giữ dashboard riêng — không ghi đè báo cáo trước.
        </p>
      </header>

      <div
        ref={listRef}
        className="flex-1 space-y-5 overflow-y-auto px-4 py-5 md:px-6 scrollbar-thin"
      >
        {messages.length === 0 && !loading ? (
          <EmptyHero onAsk={(q) => void sendQuery(q)} />
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => {
              const isUser = msg.role === "user";
              let thisReport = 0;
              if (!isUser && msg.payload) {
                reportN += 1;
                thisReport = reportN;
              }
              return (
                <motion.div
                  key={msg.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.28 }}
                  className={cn("flex flex-col gap-3", isUser && "items-end")}
                >
                  <div
                    className={cn(
                      "max-w-[92%] rounded-2xl px-4 py-3 text-[15px] leading-relaxed md:max-w-[75%]",
                      isUser
                        ? "bg-ink text-foam shadow-md shadow-ink/10"
                        : "border border-line bg-white/90 text-ink-soft",
                    )}
                  >
                    {msg.content}
                  </div>
                  {!isUser && msg.payload && (
                    <ReportCard
                      payload={msg.payload}
                      reportIndex={thisReport}
                      messageId={msg.id}
                    />
                  )}
                </motion.div>
              );
            })}
          </AnimatePresence>
        )}

        {loading && (
          <div className="flex items-center gap-3 rounded-2xl border border-line bg-white/80 px-4 py-3 text-sm text-ink-soft">
            <span className="loading-bars" aria-hidden>
              <span />
              <span />
              <span />
            </span>
            {loadingLabel}
            <Loader2 className="ml-auto h-4 w-4 animate-spin text-teal" />
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={onSubmit}
        className="border-t border-line bg-white/55 p-3 md:p-4 backdrop-blur"
      >
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-white p-2 shadow-sm focus-within:border-teal/40 focus-within:ring-2 focus-within:ring-teal/15">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void sendQuery(input);
              }
            }}
            rows={1}
            placeholder="Nhập câu hỏi phân tích dữ liệu…"
            className="max-h-36 min-h-[48px] flex-1 resize-none bg-transparent px-3 py-3 text-[15px] text-ink outline-none placeholder:text-ink-soft/45"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="mb-1 mr-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal text-white transition hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Gửi"
          >
            <ArrowUp className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-2 px-1 text-[11px] text-ink-soft/55">
          Enter để gửi · Shift+Enter xuống dòng
        </p>
      </form>
    </div>
  );
}
