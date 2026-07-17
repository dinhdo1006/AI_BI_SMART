"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { ArrowUp, Loader2, Paperclip, X } from "lucide-react";
import { postChatStream, postUploadAnalyze } from "@/lib/api";
import type { HistoryMessage } from "@/lib/types";
import { isVizOnlyRequest } from "@/lib/viz";
import { useChatStore } from "@/store/chat-store";
import { EmptyHero } from "./EmptyHero";
import { ReportCard } from "./ReportCard";
import { cn } from "@/lib/utils";

const LOADING_STEPS = [
  "Đang phân loại câu hỏi (Router)…",
  "Đang tạo SQL…",
  "Đang truy vấn cơ sở dữ liệu…",
  "Đang phân tích insight…",
  "Đang chọn biểu đồ…",
];

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
  const lastInsight = useChatStore((s) => s.lastInsight);

  const [input, setInput] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const stepTimer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, loadingLabel]);

  function clearStepTimer() {
    if (stepTimer.current) {
      clearInterval(stepTimer.current);
      stepTimer.current = null;
    }
  }

  async function sendUpload(file: File, question: string) {
    const q =
      question.trim() || `Phân tích dữ liệu từ file ${file.name}`;
    addUser(`${q}\n📎 ${file.name}`);
    setInput("");
    setUploadFile(null);
    if (fileRef.current) fileRef.current.value = "";

    setLoading(true, "Đang đọc & phân tích file upload…");
    try {
      const payload = await postUploadAnalyze({
        domainId,
        question: q,
        file,
      });
      payload.query = q;
      payload.domain_id = domainId;
      addAssistant(
        briefFromPayload(payload.status || (payload.error ? "error" : "success")),
        payload,
      );
    } catch (err) {
      addAssistant(
        err instanceof Error ? err.message : "Lỗi không xác định khi upload.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function sendQuery(raw: string) {
    const query = raw.trim();
    if (loading) return;
    if (uploadFile) {
      await sendUpload(uploadFile, query);
      return;
    }
    if (!query) return;

    addUser(query);
    setInput("");

    const history: HistoryMessage[] = useChatStore
      .getState()
      .messages.filter((m) => m.role === "user" || m.content)
      .slice(-6)
      .map((m) => ({ role: m.role, content: m.content }));

    const historyForApi = history.slice(0, -1);

    const reuse =
      isVizOnlyRequest(query) && lastData() ? lastData() : null;
    const previousInsight = reuse ? lastInsight() : "";

    if (reuse) {
      setLoading(true, "Đang đổi loại biểu đồ…");
    } else {
      let stepIdx = 0;
      setLoading(true, LOADING_STEPS[0]);
      clearStepTimer();
      stepTimer.current = setInterval(() => {
        stepIdx = Math.min(stepIdx + 1, LOADING_STEPS.length - 1);
        setLoading(true, LOADING_STEPS[stepIdx]);
      }, 2200);
    }

    try {
      const payload = await postChatStream({
        domainId,
        query,
        history: historyForApi,
        reuseData: reuse,
        previousInsight,
        onProgress: (step) => setLoading(true, step),
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
      clearStepTimer();
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
            {(() => {
              const reportIndexById = new Map<string, number>();
              let n = 0;
              for (const m of messages) {
                if (m.role !== "user" && m.payload) {
                  n += 1;
                  reportIndexById.set(m.id, n);
                }
              }
              return messages.map((msg) => {
                const isUser = msg.role === "user";
                const thisReport = reportIndexById.get(msg.id) || 0;
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
              });
            })()}
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
        {uploadFile && (
          <div className="mb-2 flex items-center gap-2 rounded-xl border border-teal/25 bg-teal/[0.06] px-3 py-2 text-xs text-ink">
            <Paperclip className="h-3.5 w-3.5 text-teal" />
            <span className="min-w-0 flex-1 truncate font-medium">
              {uploadFile.name}
            </span>
            <button
              type="button"
              onClick={() => {
                setUploadFile(null);
                if (fileRef.current) fileRef.current.value = "";
              }}
              className="rounded-md p-1 text-ink-soft hover:text-copper"
              aria-label="Bỏ file"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}
        <div className="flex items-end gap-2 rounded-2xl border border-line bg-white p-2 shadow-sm focus-within:border-teal/40 focus-within:ring-2 focus-within:ring-teal/15">
          <input
            ref={fileRef}
            type="file"
            accept=".csv,.tsv,.txt,.xlsx,.xls,.pdf"
            className="hidden"
            onChange={(e) => setUploadFile(e.target.files?.[0] || null)}
          />
          <button
            type="button"
            onClick={() => fileRef.current?.click()}
            disabled={loading}
            className="mb-1 ml-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-line bg-foam text-ink-soft transition hover:border-teal/35 hover:text-teal disabled:opacity-40"
            aria-label="Đính kèm CSV/Excel"
            title="Upload CSV/Excel để hỏi ad-hoc"
          >
            <Paperclip className="h-5 w-5" />
          </button>
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
            placeholder={
              uploadFile
                ? "Nhập câu hỏi về file (hoặc Enter để phân tích nhanh)…"
                : "Nhập câu hỏi phân tích dữ liệu…"
            }
            className="max-h-36 min-h-[48px] flex-1 resize-none bg-transparent px-3 py-3 text-[15px] text-ink outline-none placeholder:text-ink-soft/45"
          />
          <button
            type="submit"
            disabled={loading || (!input.trim() && !uploadFile)}
            className="mb-1 mr-1 flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-teal text-white transition hover:bg-teal-deep disabled:cursor-not-allowed disabled:opacity-40"
            aria-label="Gửi"
          >
            <ArrowUp className="h-5 w-5" />
          </button>
        </div>
        <p className="mt-2 px-1 text-[11px] text-ink-soft/55">
          Enter để gửi · Shift+Enter xuống dòng · kẹp giấy để upload CSV/Excel
        </p>
      </form>
    </div>
  );
}
