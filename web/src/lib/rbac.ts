/** RBAC phía client — đồng bộ tối thiểu với core/rbac.py */

export type ClientRole = "admin" | "analyst" | "viewer";

const PERMS: Record<string, ClientRole[]> = {
  chat: ["admin", "analyst", "viewer"],
  export: ["admin", "analyst"],
  "dashboard.write": ["admin", "analyst"],
  "article.write": ["admin", "analyst"],
  "article.revise": ["admin", "analyst"],
  upload: ["admin", "analyst"],
  "alerts.manage": ["admin", "analyst"],
  feedback: ["admin", "analyst", "viewer"],
  "admin.monitoring": ["admin"],
};

export function getClientRole(): ClientRole {
  if (typeof window === "undefined") return "analyst";
  const raw = (window.localStorage.getItem("abi_role") || "").toLowerCase();
  if (raw === "admin" || raw === "analyst" || raw === "viewer") return raw;
  // Chưa login (dev open) — cho phép analyst để không khóa demo
  if (!window.localStorage.getItem("abi_api_key")) return "analyst";
  return "viewer";
}

export function canClient(permission: string): boolean {
  const role = getClientRole();
  const allowed = PERMS[permission];
  if (!allowed) return role === "admin";
  return allowed.includes(role);
}
