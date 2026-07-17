"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  Activity,
  BookOpen,
  ChevronDown,
  MessageSquarePlus,
  Pencil,
  Pin,
  PinOff,
  Sparkles,
  Trash2,
} from "lucide-react";
import {
  API_BASE,
  fetchDomainExplore,
  fetchDomainsHealth,
  fetchTenantBranding,
  postLogin,
} from "@/lib/api";
import { promptsForDomain } from "@/lib/domain-prompts";
import type { DomainExplore, DomainsHealth } from "@/lib/types";
import { useChatStore, type ChatSession } from "@/store/chat-store";
import { cn } from "@/lib/utils";
import { AlertPanel } from "@/components/AlertPanel";
import { DashboardPanel } from "@/components/DashboardPanel";
import { canClient } from "@/lib/rbac";
import { AutoArticlePanel } from "@/components/AutoArticlePanel";

export function Sidebar() {
  const domains = useChatStore((s) => s.domains);
  const domainId = useChatStore((s) => s.domainId);
  const setDomainId = useChatStore((s) => s.setDomainId);
  const sessions = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const newChat = useChatStore((s) => s.newChat);
  const selectSession = useChatStore((s) => s.selectSession);
  const deleteSession = useChatStore((s) => s.deleteSession);
  const togglePinSession = useChatStore((s) => s.togglePinSession);
  const renameSession = useChatStore((s) => s.renameSession);
  const [health, setHealth] = useState<DomainsHealth | null>(null);
  const [explore, setExplore] = useState<DomainExplore | null>(null);
  const [exploreOpen, setExploreOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editTitle, setEditTitle] = useState("");
  const [brandName, setBrandName] = useState("AI BI Smart");
  const [loginOpen, setLoginOpen] = useState(false);
  const [email, setEmail] = useState("admin@local");
  const [password, setPassword] = useState("admin123");
  const [loginMsg, setLoginMsg] = useState<string | null>(null);
  const [roleLabel, setRoleLabel] = useState<string | null>(null);

  useEffect(() => {
    fetchDomainsHealth().then(setHealth);
    const t = setInterval(() => fetchDomainsHealth().then(setHealth), 60_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    fetchTenantBranding().then((b) => {
      const name = b?.branding?.product_name || b?.tenant_name || "AI BI Smart";
      setBrandName(name);
      const color = b?.branding?.primary_color;
      if (color && typeof document !== "undefined") {
        document.documentElement.style.setProperty("--color-teal", color);
      }
    });
    if (typeof window !== "undefined") {
      setRoleLabel(window.localStorage.getItem("abi_role"));
    }
  }, []);

  useEffect(() => {
    setExplore(null);
    setExploreOpen(false);
    fetchDomainExplore(domainId).then(setExplore);
  }, [domainId]);

  const suggestions = promptsForDomain(domainId);
  const domainHealth = health?.domains?.[domainId];

  function startRename(sess: ChatSession) {
    setEditingId(sess.id);
    setEditTitle(sess.title);
  }

  function commitRename() {
    if (!editingId) return;
    renameSession(editingId, editTitle);
    setEditingId(null);
  }

  async function onLogin() {
    setLoginMsg(null);
    const res = await postLogin({ email, password });
    if (!res.ok || !res.api_key) {
      setLoginMsg(res.error || "Đăng nhập thất bại");
      return;
    }
    window.localStorage.setItem("abi_api_key", res.api_key);
    if (res.role) {
      window.localStorage.setItem("abi_role", res.role);
      setRoleLabel(res.role);
    }
    const name =
      res.tenant?.branding?.product_name ||
      res.tenant?.name ||
      brandName;
    setBrandName(name);
    setLoginOpen(false);
    setLoginMsg("Đã đăng nhập");
  }

  function onLogout() {
    window.localStorage.removeItem("abi_api_key");
    window.localStorage.removeItem("abi_role");
    setRoleLabel(null);
    setLoginMsg(null);
  }

  return (
    <div className="flex h-full flex-col overflow-hidden rounded-[22px] border border-line bg-foam/80 shadow-[var(--shadow)] backdrop-blur-md">
      <div className="relative overflow-hidden border-b border-line px-5 pb-4 pt-6">
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
          {brandName}
        </h1>
        <p className="mt-2 max-w-[16rem] text-sm leading-relaxed text-ink-soft/85">
          Hỏi bằng tiếng Việt — nhận SQL, dashboard và bài phân tích.
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => setLoginOpen((v) => !v)}
            className="rounded-lg border border-line bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-teal"
          >
            {roleLabel ? `Role: ${roleLabel}` : "Đăng nhập tenant"}
          </button>
          {roleLabel && (
            <button
              type="button"
              onClick={onLogout}
              className="rounded-lg border border-line bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-copper"
            >
              Thoát
            </button>
          )}
          {roleLabel === "admin" && (
            <a
              href="/monitoring"
              target="_blank"
              rel="noreferrer"
              className="rounded-lg border border-line bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-teal"
            >
              Monitoring
            </a>
          )}
          <a
            href="/api/v1/sso/login"
            className="rounded-lg border border-line bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-teal"
            title="Cần SSO_PROVIDER=oidc|saml trong .env"
          >
            SSO
          </a>
          <a
            href="/data-quality"
            target="_blank"
            rel="noreferrer"
            className="rounded-lg border border-line bg-white/90 px-2.5 py-1 text-[11px] font-semibold text-ink-soft hover:text-teal"
          >
            Data quality
          </a>
        </div>
        {loginOpen && (
          <div className="mt-2 space-y-2 rounded-xl border border-line bg-white/95 p-3">
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Email"
              className="w-full rounded-lg border border-line px-2 py-1.5 text-xs outline-none focus:border-teal/40"
            />
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Mật khẩu"
              className="w-full rounded-lg border border-line px-2 py-1.5 text-xs outline-none focus:border-teal/40"
            />
            <button
              type="button"
              onClick={() => void onLogin()}
              className="w-full rounded-lg bg-teal px-2 py-1.5 text-xs font-semibold text-white"
            >
              Đăng nhập
            </button>
            {loginMsg && (
              <p className="text-[11px] text-ink-soft">{loginMsg}</p>
            )}
          </div>
        )}
        <button
          type="button"
          onClick={() => newChat()}
          className="mt-4 flex w-full items-center justify-center gap-2 rounded-xl bg-teal px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-teal-deep"
        >
          <MessageSquarePlus className="h-4 w-4" />
          Chat mới
        </button>
      </div>

      <div className="flex flex-1 flex-col gap-4 overflow-y-auto p-4 scrollbar-thin">
        <label className="block px-1">
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

        {explore && explore.tables.length > 0 && (
          <div className="rounded-xl border border-line bg-white/70">
            <button
              type="button"
              onClick={() => setExploreOpen((v) => !v)}
              className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left"
            >
              <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
                <BookOpen className="h-3.5 w-3.5 text-teal" />
                Domain có gì ({explore.table_count} bảng)
              </span>
              <ChevronDown
                className={cn(
                  "h-4 w-4 text-ink-soft transition",
                  exploreOpen && "rotate-180",
                )}
              />
            </button>
            {exploreOpen && (
              <ul className="max-h-48 space-y-2 overflow-y-auto border-t border-line px-3 py-2.5 scrollbar-thin">
                {explore.tables.map((t) => (
                  <li key={t.name}>
                    <p className="text-[13px] font-semibold text-ink">
                      {t.name}
                    </p>
                    {t.description ? (
                      <p className="mt-0.5 text-[11px] leading-snug text-ink-soft/70">
                        {t.description}
                      </p>
                    ) : null}
                    <p className="mt-1 text-[10px] text-ink-soft/55">
                      {t.columns
                        .slice(0, 6)
                        .map((c) => c.label)
                        .join(" · ")}
                      {t.columns.length > 6
                        ? ` · +${t.columns.length - 6}`
                        : ""}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}

        {canClient("alerts.manage") && <AlertPanel domainId={domainId} />}
        <DashboardPanel domainId={domainId} />
        <AutoArticlePanel domainId={domainId} />

        <div>
          <div className="mb-2 flex items-center justify-between px-1">
            <span className="text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
              Cuộc trò chuyện
            </span>
            <span className="text-[10px] text-ink-soft/50">{sessions.length}</span>
          </div>
          <ul className="space-y-1">
            {sessions.map((sess) => {
              const active = sess.id === activeSessionId;
              return (
                <li key={sess.id}>
                  <div
                    className={cn(
                      "group rounded-xl border px-2 py-1.5 transition",
                      active
                        ? "border-teal/35 bg-teal/10"
                        : "border-transparent bg-mist/50 hover:border-line hover:bg-white",
                    )}
                  >
                    <div className="flex items-start gap-1">
                      <button
                        type="button"
                        onClick={() => selectSession(sess.id)}
                        className="min-w-0 flex-1 px-1 py-1 text-left"
                      >
                        {editingId === sess.id ? (
                          <input
                            autoFocus
                            value={editTitle}
                            onChange={(e) => setEditTitle(e.target.value)}
                            onBlur={commitRename}
                            onClick={(e) => e.stopPropagation()}
                            onKeyDown={(e) => {
                              if (e.key === "Enter") commitRename();
                              if (e.key === "Escape") setEditingId(null);
                            }}
                            className="w-full rounded-md border border-teal/40 bg-white px-1.5 py-0.5 text-[13px] text-ink outline-none"
                          />
                        ) : (
                          <>
                            <p className="truncate text-[13px] font-medium text-ink">
                              {sess.pinned ? "📌 " : ""}
                              {sess.title}
                            </p>
                            <p className="mt-0.5 truncate text-[10px] text-ink-soft/55">
                              {formatSessionMeta(sess)}
                            </p>
                          </>
                        )}
                      </button>
                      <div className="flex shrink-0 gap-0.5 opacity-100 sm:opacity-0 sm:group-hover:opacity-100">
                        <IconBtn
                          label={sess.pinned ? "Bỏ ghim" : "Ghim"}
                          onClick={() => togglePinSession(sess.id)}
                        >
                          {sess.pinned ? (
                            <PinOff className="h-3.5 w-3.5" />
                          ) : (
                            <Pin className="h-3.5 w-3.5" />
                          )}
                        </IconBtn>
                        <IconBtn
                          label="Đổi tên"
                          onClick={() => startRename(sess)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </IconBtn>
                        <IconBtn
                          label="Xóa chat"
                          danger
                          onClick={() => {
                            if (
                              window.confirm(
                                `Xóa cuộc chat “${sess.title}”?`,
                              )
                            ) {
                              deleteSession(sess.id);
                            }
                          }}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </IconBtn>
                      </div>
                    </div>
                  </div>
                </li>
              );
            })}
          </ul>
        </div>

        <div>
          <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
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
    </div>
  );
}

function formatSessionMeta(sess: ChatSession): string {
  const n = sess.messages.length;
  const when = new Date(sess.updatedAt);
  const time = when.toLocaleString("vi-VN", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
  return `${n} tin · ${time}`;
}

function IconBtn({
  children,
  onClick,
  label,
  danger,
}: {
  children: ReactNode;
  onClick: () => void;
  label: string;
  danger?: boolean;
}) {
  return (
    <button
      type="button"
      title={label}
      aria-label={label}
      onClick={(e) => {
        e.stopPropagation();
        onClick();
      }}
      className={cn(
        "inline-flex h-7 w-7 items-center justify-center rounded-lg text-ink-soft transition hover:bg-white",
        danger ? "hover:text-copper" : "hover:text-ink",
      )}
    >
      {children}
    </button>
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
