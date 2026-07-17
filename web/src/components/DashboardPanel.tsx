"use client";

import { useCallback, useEffect, useState } from "react";
import { ChevronDown, ExternalLink, LayoutDashboard, Trash2 } from "lucide-react";
import {
  deleteDashboard,
  fetchDashboards,
  setDashboardPublic,
  type DashboardListItem,
} from "@/lib/api";
import { canClient } from "@/lib/rbac";
import { cn } from "@/lib/utils";

function formatWhen(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString("vi-VN", {
      day: "2-digit",
      month: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return iso.slice(0, 16);
  }
}

export function DashboardPanel({ domainId }: { domainId: string }) {
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<DashboardListItem[]>([]);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const canWrite = canClient("dashboard.write");
  const canRead = canClient("dashboard.read");

  const reload = useCallback(async () => {
    if (!canRead) return;
    setError(null);
    const list = await fetchDashboards(domainId);
    setItems(list);
  }, [domainId, canRead]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void reload();
    }, 0);
    return () => window.clearTimeout(timer);
  }, [domainId, reload]);

  useEffect(() => {
    const onSaved = () => void reload();
    window.addEventListener("abi:dashboard-saved", onSaved);
    return () => window.removeEventListener("abi:dashboard-saved", onSaved);
  }, [reload]);

  if (!canRead) return null;

  async function togglePublic(id: string, next: boolean) {
    if (!canWrite) return;
    setBusyId(id);
    setError(null);
    try {
      await setDashboardPublic(id, next);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không đổi được public");
    } finally {
      setBusyId(null);
    }
  }

  async function onDelete(id: string) {
    if (!canWrite) return;
    if (!window.confirm("Xóa dashboard này?")) return;
    setBusyId(id);
    setError(null);
    const ok = await deleteDashboard(id);
    if (!ok) setError("Không xóa được dashboard");
    else await reload();
    setBusyId(null);
  }

  return (
    <div className="rounded-xl border border-line bg-white/70">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-2 px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-ink-soft/70">
          <LayoutDashboard className="h-3.5 w-3.5 text-teal" />
          Dashboard đã lưu ({items.length})
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-ink-soft transition",
            open && "rotate-180",
          )}
        />
      </button>
      {open && (
        <div className="space-y-2 border-t border-line px-3 py-2.5">
          {error && (
            <p className="rounded-md bg-copper-soft/40 px-2 py-1 text-[11px] text-copper">
              {error}
            </p>
          )}
          {items.length === 0 ? (
            <p className="text-[11px] text-ink-soft/60">
              Chưa có dashboard — lưu từ báo cáo trong chat.
            </p>
          ) : (
            <ul className="max-h-52 space-y-1.5 overflow-y-auto scrollbar-thin">
              {items.map((d) => (
                <li
                  key={d.id}
                  className="rounded-lg border border-line bg-white px-2 py-1.5 text-[11px]"
                >
                  <div className="flex items-start justify-between gap-1">
                    <div className="min-w-0">
                      <p className="truncate font-semibold text-ink">{d.title}</p>
                      <p className="mt-0.5 text-ink-soft/65">
                        {d.report_count} báo cáo · {formatWhen(d.created_at)}
                        {d.is_public ? " · công khai" : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-0.5">
                      <a
                        href={`/dashboard/${d.id}`}
                        target="_blank"
                        rel="noreferrer"
                        title="Mở dashboard"
                        className="rounded p-1 text-ink-soft hover:text-teal"
                      >
                        <ExternalLink className="h-3 w-3" />
                      </a>
                      {canWrite && (
                        <>
                          <button
                            type="button"
                            disabled={busyId === d.id}
                            title={d.is_public ? "Tắt public" : "Bật public"}
                            onClick={() => void togglePublic(d.id, !d.is_public)}
                            className={cn(
                              "rounded px-1.5 py-0.5 text-[10px] font-bold",
                              d.is_public
                                ? "bg-teal/15 text-teal"
                                : "bg-mist text-ink-soft",
                            )}
                          >
                            {d.is_public ? "PUB" : "PRIV"}
                          </button>
                          <button
                            type="button"
                            disabled={busyId === d.id}
                            title="Xóa"
                            onClick={() => void onDelete(d.id)}
                            className="rounded p-1 text-ink-soft hover:text-copper"
                          >
                            <Trash2 className="h-3 w-3" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  {d.is_public && (
                    <a
                      href={`/embed/${d.id}`}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1 inline-block text-[10px] font-medium text-teal underline"
                    >
                      Link embed →
                    </a>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
