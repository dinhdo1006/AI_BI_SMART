"use client";

import { useEffect, useState } from "react";
import { Activity, Eraser, Sparkles } from "lucide-react";
import { API_BASE, fetchDomainsHealth } from "@/lib/api";
import { promptsForDomain } from "@/lib/domain-prompts";
import type { DomainsHealth } from "@/lib/types";
import { useChatStore } from "@/store/chat-store";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const domains = useChatStore((s) => s.domains);
  const domainId = useChatStore((s) => s.domainId);
  const setDomainId = useChatStore((s) => s.setDomainId);
  const clearAll = useChatStore((s) => s.clearAll);
  const [health, setHealth] = useState<DomainsHealth | null>(null);

  useEffect(() => {
    fetchDomainsHealth().then(setHealth);
    const t = setInterval(() => fetchDomainsHealth().then(setHealth), 60_000);
    return () => clearInterval(t);
  }, []);

  const suggestions = promptsForDomain(domainId);
  const domainHealth = health?.domains?.[domainId];

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[22px] border border-line bg-foam/80 shadow-[var(--shadow)] backdrop-blur-md">
      <div className="relative overflow-hidden border-b border-line px-5 pb-5 pt-6">
        <div
          className="pointer-events-none absolute -right-8 -top-10 h-36 w-36 rounded-full opacity-70"
          style={{
            background:
              "radial-gradient(circle, rgba(15,118,110,0.28), transparent 70%)",
          }}
        />
        <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-teal">
          Workspace
        </p>
        <h1 className="mt-2 font-[family-name:var(--font-display)] text-[1.85rem] font-extrabold leading-[1.05] tracking-tight text-ink">
          AI BI Smart
        </h1>
        <p className="mt-2 max-w-[16rem] text-sm leading-relaxed text-ink-soft/85">
          Hỏi bằng tiếng Việt — nhận SQL, dashboard và bài phân tích.
        </p>
      </div>

      <div className="flex flex-1 flex-col gap-5 overflow-y-auto p-5 scrollbar-thin">
        <label className="block">
          <span className="mb-2 block text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
            Domain dữ liệu
          </span>
          <select
            value={domainId}
            onChange={(e) => setDomainId(e.target.value)}
            className="w-full appearance-none rounded-xl border border-line bg-white px-3 py-2.5 text-sm font-medium text-ink outline-none transition focus:border-teal focus:ring-2 focus:ring-teal/20"
          >
            {domains.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>

        <div>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
            <Sparkles className="h-3.5 w-3.5 text-copper" />
            Gợi ý hỏi
          </div>
          <ul className="space-y-2">
            {suggestions.map((q) => (
              <li key={q}>
                <button
                  type="button"
                  onClick={() => {
                    window.dispatchEvent(
                      new CustomEvent("abi:suggest", { detail: q }),
                    );
                  }}
                  className="w-full rounded-xl border border-transparent bg-mist/70 px-3 py-2.5 text-left text-[13px] leading-snug text-ink-soft transition hover:border-teal/25 hover:bg-white hover:text-ink"
                >
                  {q}
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-xl border border-line bg-white/70 p-3">
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
            <Activity className="h-3.5 w-3.5" />
            Trạng thái
          </div>
          <StatusRow
            ok={Boolean(health)}
            label="API backend"
            detail={health ? "hoạt động" : "không kết nối"}
          />
          <StatusRow
            ok={Boolean(domainHealth?.db_ok)}
            label={`DB ${domainId}`}
            detail={
              domainHealth?.db_ok
                ? `OK · ${domainHealth.dialect || "db"}`
                : domainHealth?.detail || "chưa kiểm tra"
            }
          />
          {health?.schema_rag_enabled != null && (
            <p className="mt-2 text-[11px] text-ink-soft/65">
              Schema RAG: {health.schema_rag_enabled ? "bật" : "tắt"}
            </p>
          )}
          <p className="mt-2 truncate text-[11px] text-ink-soft/55">
            {API_BASE || "proxy → /api (cùng origin)"}
          </p>
        </div>
      </div>

      <div className="border-t border-line p-4">
        <button
          type="button"
          onClick={clearAll}
          className={cn(
            "flex w-full items-center justify-center gap-2 rounded-xl border border-line bg-white px-3 py-2.5",
            "text-sm font-semibold text-ink-soft transition hover:border-copper/40 hover:text-copper",
          )}
        >
          <Eraser className="h-4 w-4" />
          Xóa lịch sử
        </button>
      </div>
    </div>
  );
}

function StatusRow({
  ok,
  label,
  detail,
}: {
  ok: boolean;
  label: string;
  detail: string;
}) {
  return (
    <div className="flex items-start gap-2 py-1 text-[12.5px]">
      <span
        className={cn(
          "mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full",
          ok ? "bg-teal" : "bg-copper",
        )}
      />
      <div className="min-w-0">
        <p className="font-medium text-ink">{label}</p>
        <p className="truncate text-ink-soft/70">{detail}</p>
      </div>
    </div>
  );
}
