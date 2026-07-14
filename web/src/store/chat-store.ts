"use client";

import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import type { ChatMessage, ChatResponse, DomainItem } from "@/lib/types";
import { uid } from "@/lib/utils";

// Giới hạn số tin nhắn lưu localStorage — tránh vượt quota ~5MB
const MAX_PERSISTED_MESSAGES = 60;

type ChatState = {
  domains: DomainItem[];
  domainId: string;
  messages: ChatMessage[];
  loading: boolean;
  loadingLabel: string;
  setDomains: (domains: DomainItem[]) => void;
  setDomainId: (id: string) => void;
  clearAll: () => void;
  addUser: (content: string) => string;
  addAssistant: (content: string, payload?: ChatResponse) => string;
  updateMessage: (id: string, patch: Partial<ChatMessage>) => void;
  setLoading: (loading: boolean, label?: string) => void;
  lastData: () => Record<string, unknown>[] | null;
  lastInsight: () => string;
};

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      domains: [],
      domainId: "finance_vnfdata",
      messages: [],
      loading: false,
      loadingLabel: "Đang phân tích…",

      setDomains: (domains) =>
        set({
          domains,
          domainId: domains[0]?.id || "finance_vnfdata",
        }),

      setDomainId: (id) =>
        set({
          domainId: id,
          messages: [],
        }),

      clearAll: () => set({ messages: [] }),

      addUser: (content) => {
        const id = uid("u");
        set((s) => ({
          messages: [...s.messages, { id, role: "user", content }],
        }));
        return id;
      },

      addAssistant: (content, payload) => {
        const id = uid("a");
        set((s) => {
          const next = [...s.messages, { id, role: "assistant" as const, content, payload }];
          return {
            messages: next.slice(-MAX_PERSISTED_MESSAGES),
          };
        });
        return id;
      },

      updateMessage: (id, patch) =>
        set((s) => ({
          messages: s.messages.map((m) => (m.id === id ? { ...m, ...patch } : m)),
        })),

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
      storage: createJSONStorage(() => localStorage),
      // Chỉ persist những field cần thiết — bỏ loading state
      partialize: (state) => ({
        domainId: state.domainId,
        messages: state.messages,
      }),
    },
  ),
);
