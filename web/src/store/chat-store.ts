"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ChatMessage, ChatResponse, DomainItem } from "@/lib/types";
import { uid } from "@/lib/utils";

const MAX_MESSAGES_PER_SESSION = 50;
const MAX_SESSIONS = 40;

export type ChatSession = {
  id: string;
  title: string;
  domainId: string;
  messages: ChatMessage[];
  pinned: boolean;
  createdAt: number;
  updatedAt: number;
};

type ChatState = {
  domains: DomainItem[];
  domainId: string;
  sessions: ChatSession[];
  activeSessionId: string;
  /** Mirror tin nhắn session đang mở — tương thích ChatPanel / ReportCard */
  messages: ChatMessage[];
  loading: boolean;
  loadingLabel: string;

  setDomains: (domains: DomainItem[]) => void;
  setDomainId: (id: string) => void;

  newChat: () => string;
  selectSession: (id: string) => void;
  deleteSession: (id: string) => void;
  togglePinSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;

  /** @deprecated dùng deleteSession(active) — giữ để không vỡ import cũ */
  clearAll: () => void;

  addUser: (content: string) => string;
  addAssistant: (content: string, payload?: ChatResponse) => string;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  setLoading: (loading: boolean, label?: string) => void;
  lastData: () => Record<string, unknown>[] | null;
  lastInsight: () => string;
};

function titleFromMessages(messages: ChatMessage[]): string {
  const firstUser = messages.find((m) => m.role === "user" && m.content.trim());
  if (!firstUser) return "Cuộc trò chuyện mới";
  const t = firstUser.content.trim().replace(/\s+/g, " ");
  return t.length > 48 ? `${t.slice(0, 46)}…` : t;
}

function makeSession(domainId: string, messages: ChatMessage[] = []): ChatSession {
  const now = Date.now();
  return {
    id: uid("chat"),
    title: titleFromMessages(messages),
    domainId,
    messages,
    pinned: false,
    createdAt: now,
    updatedAt: now,
  };
}

function sortSessions(list: ChatSession[]): ChatSession[] {
  return [...list].sort((a, b) => {
    if (a.pinned !== b.pinned) return a.pinned ? -1 : 1;
    return b.updatedAt - a.updatedAt;
  });
}

function withActive(
  sessions: ChatSession[],
  activeSessionId: string,
  domainFallback: string,
): Pick<ChatState, "sessions" | "activeSessionId" | "messages" | "domainId"> {
  let list = sessions;
  let active = list.find((s) => s.id === activeSessionId);
  if (!active) {
    if (!list.length) {
      const created = makeSession(domainFallback);
      list = [created];
      active = created;
    } else {
      active = list[0];
    }
  }
  return {
    sessions: sortSessions(list),
    activeSessionId: active.id,
    messages: active.messages,
    domainId: active.domainId || domainFallback,
  };
}

function mapActive(
  state: ChatState,
  updater: (sess: ChatSession) => ChatSession,
): Partial<ChatState> {
  const nextSessions = state.sessions.map((s) =>
    s.id === state.activeSessionId ? updater(s) : s,
  );
  return withActive(nextSessions, state.activeSessionId, state.domainId);
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      domains: [],
      domainId: "finance_vnfdata",
      sessions: [],
      activeSessionId: "",
      messages: [],
      loading: false,
      loadingLabel: "Đang phân tích…",

      setDomains: (domains) =>
        set((s) => {
          const preferred = domains[0]?.id || s.domainId || "finance_vnfdata";
          if (!s.sessions.length) {
            const created = makeSession(preferred);
            return {
              domains,
              ...withActive([created], created.id, preferred),
            };
          }
          return { domains };
        }),

      setDomainId: (id) =>
        set((s) => ({
          ...mapActive(s, (sess) => ({
            ...sess,
            domainId: id,
            updatedAt: Date.now(),
          })),
        })),

      newChat: () => {
        const domainId = get().domainId || "finance_vnfdata";
        const created = makeSession(domainId);
        set((s) => {
          let sessions = [created, ...s.sessions];
          if (sessions.length > MAX_SESSIONS) {
            // Xóa session cũ nhất không pin
            const removable = [...sessions]
              .reverse()
              .find((x) => !x.pinned && x.id !== created.id);
            if (removable) {
              sessions = sessions.filter((x) => x.id !== removable.id);
            } else {
              sessions = sessions.slice(0, MAX_SESSIONS);
            }
          }
          return {
            ...withActive(sessions, created.id, domainId),
            loading: false,
          };
        });
        return created.id;
      },

      selectSession: (id) =>
        set((s) => withActive(s.sessions, id, s.domainId)),

      deleteSession: (id) =>
        set((s) => {
          const remaining = s.sessions.filter((x) => x.id !== id);
          if (!remaining.length) {
            const created = makeSession(s.domainId);
            return withActive([created], created.id, s.domainId);
          }
          const nextActive =
            s.activeSessionId === id ? remaining[0].id : s.activeSessionId;
          return withActive(remaining, nextActive, s.domainId);
        }),

      togglePinSession: (id) =>
        set((s) => {
          const sessions = s.sessions.map((x) =>
            x.id === id ? { ...x, pinned: !x.pinned, updatedAt: Date.now() } : x,
          );
          return withActive(sessions, s.activeSessionId, s.domainId);
        }),

      renameSession: (id, title) =>
        set((s) => {
          const clean = title.trim() || "Cuộc trò chuyện mới";
          const sessions = s.sessions.map((x) =>
            x.id === id
              ? { ...x, title: clean.slice(0, 80), updatedAt: Date.now() }
              : x,
          );
          return withActive(sessions, s.activeSessionId, s.domainId);
        }),

      clearAll: () => get().deleteSession(get().activeSessionId),

      addUser: (content) => {
        const id = uid("u");
        set((s) =>
          mapActive(s, (sess) => {
            const messages = [
              ...sess.messages,
              { id, role: "user" as const, content },
            ].slice(-MAX_MESSAGES_PER_SESSION);
            const title =
              sess.messages.some((m) => m.role === "user")
                ? sess.title
                : titleFromMessages(messages);
            return {
              ...sess,
              messages,
              title,
              updatedAt: Date.now(),
            };
          }),
        );
        return id;
      },

      addAssistant: (content, payload) => {
        const id = uid("a");
        set((s) =>
          mapActive(s, (sess) => {
            const messages = [
              ...sess.messages,
              {
                id,
                role: "assistant" as const,
                content,
                payload,
              },
            ].slice(-MAX_MESSAGES_PER_SESSION);
            return { ...sess, messages, updatedAt: Date.now() };
          }),
        );
        return id;
      },

      updateMessage: (id, patch) =>
        set((s) =>
          mapActive(s, (sess) => ({
            ...sess,
            messages: sess.messages.map((m) =>
              m.id === id ? { ...m, ...patch } : m,
            ),
            updatedAt: Date.now(),
          })),
        ),

      setLoading: (loading, label) =>
        set({
          loading,
          loadingLabel: label || "Đang phân tích…",
        }),

      lastData: () => {
        const msgs = get().messages;
        for (let i = msgs.length - 1; i >= 0; i--) {
          const d = msgs[i].payload?.data;
          if (d && d.length) return d;
        }
        return null;
      },

      lastInsight: () => {
        const msgs = get().messages;
        for (let i = msgs.length - 1; i >= 0; i--) {
          const p = msgs[i].payload;
          if (p?.insight && !p.viz_only) return p.insight;
        }
        return "";
      },
    }),
    {
      name: "ai-bi-smart-chat",
      version: 2,
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({
        domainId: state.domainId,
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
      }),
      migrate: (persisted, version) => {
        const p = (persisted || {}) as Record<string, unknown>;
        if (version < 2) {
          const domainId = String(p.domainId || "finance_vnfdata");
          const oldMessages = (p.messages as ChatMessage[]) || [];
          const created = makeSession(domainId, oldMessages);
          return {
            domainId,
            sessions: [created],
            activeSessionId: created.id,
          };
        }
        return p as {
          domainId: string;
          sessions: ChatSession[];
          activeSessionId: string;
        };
      },
      onRehydrateStorage: () => (state) => {
        if (!state) return;
        if (!state.sessions?.length) {
          const created = makeSession(state.domainId || "finance_vnfdata");
          state.sessions = [created];
          state.activeSessionId = created.id;
          state.messages = [];
          state.domainId = created.domainId;
          return;
        }
        const synced = withActive(
          state.sessions,
          state.activeSessionId,
          state.domainId || "finance_vnfdata",
        );
        state.sessions = synced.sessions;
        state.activeSessionId = synced.activeSessionId;
        state.messages = synced.messages;
        state.domainId = synced.domainId;
      },
    },
  ),
);
