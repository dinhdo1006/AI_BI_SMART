"use client";

import { useEffect } from "react";
import { motion } from "framer-motion";
import { fetchDomains } from "@/lib/api";
import { useChatStore } from "@/store/chat-store";
import { Sidebar } from "./Sidebar";
import { ChatPanel } from "./ChatPanel";

function MobileDomainSelect() {
  const domains = useChatStore((s) => s.domains);
  const domainId = useChatStore((s) => s.domainId);
  const setDomainId = useChatStore((s) => s.setDomainId);
  return (
    <select
      value={domainId}
      onChange={(e) => setDomainId(e.target.value)}
      className="max-w-[160px] rounded-xl border border-line bg-white/90 px-2 py-2 text-xs font-medium text-ink outline-none"
    >
      {domains.map((d) => (
        <option key={d.id} value={d.id}>
          {d.name}
        </option>
      ))}
    </select>
  );
}

export function Workspace() {
  const setDomains = useChatStore((s) => s.setDomains);

  useEffect(() => {
    fetchDomains().then(setDomains);
  }, [setDomains]);

  return (
    <div className="relative mx-auto flex h-dvh max-w-[1600px] gap-4 p-3 md:p-5">
      <motion.aside
        initial={{ opacity: 0, x: -16 }}
        animate={{ opacity: 1, x: 0 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="hidden w-[280px] shrink-0 lg:block"
      >
        <Sidebar />
      </motion.aside>

      <motion.main
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, delay: 0.08, ease: [0.22, 1, 0.36, 1] }}
        className="flex min-w-0 flex-1 flex-col"
      >
        <div className="mb-3 flex items-end justify-between gap-3 lg:hidden">
          <div>
            <p className="font-[family-name:var(--font-display)] text-2xl font-bold tracking-tight text-ink">
              AI BI Smart
            </p>
            <p className="text-sm text-ink-soft/80">Conversational analytics</p>
          </div>
          <MobileDomainSelect />
        </div>
        <ChatPanel />
      </motion.main>
    </div>
  );
}
