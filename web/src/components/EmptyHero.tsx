"use client";

import { motion } from "framer-motion";
import { promptsForDomain } from "@/lib/domain-prompts";
import { useChatStore } from "@/store/chat-store";

export function EmptyHero({ onAsk }: { onAsk: (q: string) => void }) {
  const domainId = useChatStore((s) => s.domainId);
  const prompts = promptsForDomain(domainId);

  return (
    <div className="relative flex min-h-[58vh] flex-col items-center justify-center px-2 text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.96 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.55, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-2xl"
      >
        <div
          className="pointer-events-none absolute left-1/2 top-1/2 h-[280px] w-[280px] -translate-x-1/2 -translate-y-1/2 rounded-full opacity-80"
          style={{
            background:
              "radial-gradient(circle, rgba(15,118,110,0.18), transparent 68%)",
          }}
        />
        <p className="relative text-[11px] font-semibold uppercase tracking-[0.28em] text-teal">
          Conversational BI
        </p>
        <h2 className="relative mt-3 font-[family-name:var(--font-display)] text-4xl font-extrabold tracking-tight text-ink md:text-5xl">
          AI BI Smart
        </h2>
        <p className="relative mx-auto mt-4 max-w-md text-base leading-relaxed text-ink-soft/85">
          Đặt câu hỏi bằng tiếng Việt — hệ thống truy vấn dữ liệu, vẽ biểu đồ
          và viết phân tích giúp bạn.
        </p>

        <div className="relative mt-8 flex flex-wrap items-center justify-center gap-2">
          {prompts.map((q, i) => (
            <motion.button
              key={q}
              type="button"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 + i * 0.07 }}
              onClick={() => onAsk(q)}
              className="rounded-xl border border-line bg-white/90 px-4 py-2 text-sm text-ink-soft transition hover:border-teal/35 hover:text-ink"
            >
              {q}
            </motion.button>
          ))}
        </div>
      </motion.div>
    </div>
  );
}
