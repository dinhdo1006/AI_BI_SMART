"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { MessageSquarePlus } from "lucide-react";
import { fetchDomains } from "@/lib/api";
import { useChatStore } from "@/store/chat-store";
import { Sidebar } from "./Sidebar";
import { ChatPanel } from "./ChatPanel";

function MobileChrome() {
  const domains = useChatStore((s) => s.domains);
  const domainId = useChatStore((s) => s.domainId);
  const setDomainId = useChatStore((s) => s.setDomainId);
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const selectSession = useChatStore((s) => s.selectSession);
  const newChat = useChatStore((s) => s.newChat);
  const [showSessions, setShowSessions] = useState(false);

  return (
    <div className="mb-3 space-y-2 lg:hidden">
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-ink">
            AI BI Smart
          </p>
          <p className="text-sm text-ink-soft/80">Conversational analytics</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => newChat()}
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl bg-teal text-white"
            aria-label="Chat mới"
            title="Chat mới"
          >
            <MessageSquarePlus className="h-4 w-4" />
          </button>
          <select
            value={domainId}
            onChange={(e) => setDomainId(e.target.value)}
            className="max-w-[140px] rounded-xl border border-line bg-white/90 px-2 py-2 text-xs font-medium text-ink outline-none"
          >
            {domains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
      </div>
      <button
        type="button"
        onClick={() => setShowSessions((v) => !v)}
        className="w-full rounded-xl border border-line bg-white/90 px-3 py-2 text-left text-xs font-semibold text-ink-soft"
      >
        {showSessions ? "Ẩn danh sách chat" : "Cuộc trò chuyện đã lưu"}
      </button>
      {showSessions && (
        <ul className="max-h-40 space-y-1 overflow-y-auto rounded-xl border border-line bg-white/95 p-2">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                type="button"
                onClick={() => {
                  selectSession(s.id);
                  setShowSessions(false);
                }}
                className={`w-full rounded-lg px-2 py-1.5 text-left text-[13px] ${
                  s.id === activeSessionId
                    ? "bg-teal/10 font-semibold text-teal"
                    : "text-ink-soft hover:bg-mist"
                }`}
              >
                {s.pinned ? "📌 " : ""}
                {s.title}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function Workspace() {
  const setDomains = useChatStore((s) => s.setDomains);

  useEffect(() => {
    fetchDomains().then(setDomains);
  }, [setDomains]);

  return (
    <div className="relative flex h-dvh gap-0 p-3 md:gap-4 md:p-5">
      <motion.aside
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="hidden w-[380px] shrink-0 lg:block"
      >
        <Sidebar />
      </motion.aside>

      <motion.main
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
        className="flex min-w-0 flex-1 flex-col"
      >
        <MobileChrome />
        <ChatPanel />
      </motion.main>
    </div>
  );
}
