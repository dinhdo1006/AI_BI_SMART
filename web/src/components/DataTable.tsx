"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, Search } from "lucide-react";
import { formatNumber } from "@/lib/format";
import { cn } from "@/lib/utils";

const PAGE_SIZE = 20;

type SortDir = "asc" | "desc" | null;

function compareValues(a: unknown, b: unknown): number {
  if (a == null && b == null) return 0;
  if (a == null) return 1;
  if (b == null) return -1;
  const na = Number(a);
  const nb = Number(b);
  if (Number.isFinite(na) && Number.isFinite(nb)) return na - nb;
  return String(a).localeCompare(String(b), "vi", { numeric: true });
}

export function DataTable({ data }: { data: Record<string, unknown>[] }) {
  const [search, setSearch] = useState("");
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>(null);
  const [page, setPage] = useState(0);

  const cols = useMemo(
    () => (data.length ? Object.keys(data[0]) : []),
    [data],
  );

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    let rows = data;
    if (q) {
      rows = data.filter((row) =>
        cols.some((c) => String(row[c] ?? "").toLowerCase().includes(q)),
      );
    }
    if (sortCol && sortDir) {
      rows = [...rows].sort((a, b) => {
        const cmp = compareValues(a[sortCol], b[sortCol]);
        return sortDir === "asc" ? cmp : -cmp;
      });
    }
    return rows;
  }, [data, cols, search, sortCol, sortDir]);

  const pageCount = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, pageCount - 1);
  const pageRows = filtered.slice(
    safePage * PAGE_SIZE,
    safePage * PAGE_SIZE + PAGE_SIZE,
  );

  function toggleSort(col: string) {
    if (sortCol !== col) {
      setSortCol(col);
      setSortDir("asc");
      return;
    }
    if (sortDir === "asc") setSortDir("desc");
    else if (sortDir === "desc") {
      setSortCol(null);
      setSortDir(null);
    } else setSortDir("asc");
  }

  if (!data.length) return null;

  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className="flex items-center gap-2 border-b border-line bg-foam/60 px-3 py-2">
        <Search className="h-3.5 w-3.5 shrink-0 text-ink-soft/50" />
        <input
          type="search"
          value={search}
          onChange={(e) => {
            setSearch(e.target.value);
            setPage(0);
          }}
          placeholder="Tìm trong bảng…"
          className="w-full bg-transparent text-sm text-ink outline-none placeholder:text-ink-soft/45"
        />
        <span className="shrink-0 text-[11px] tabular-nums text-ink-soft/55">
          {filtered.length}/{data.length}
        </span>
      </div>

      <div className="max-h-[320px] overflow-auto scrollbar-thin">
        <table className="w-full min-w-[420px] border-collapse text-left text-[13px]">
          <thead className="sticky top-0 bg-mist/95 backdrop-blur">
            <tr>
              {cols.map((c) => {
                const active = sortCol === c;
                return (
                  <th key={c} className="border-b border-line px-1 py-1">
                    <button
                      type="button"
                      onClick={() => toggleSort(c)}
                      className={cn(
                        "inline-flex w-full items-center gap-1 rounded-lg px-2 py-1.5 font-semibold transition hover:bg-white/70",
                        active ? "text-teal" : "text-ink-soft",
                      )}
                    >
                      <span className="truncate">{c}</span>
                      {active && sortDir === "asc" ? (
                        <ArrowUp className="h-3 w-3 shrink-0" />
                      ) : active && sortDir === "desc" ? (
                        <ArrowDown className="h-3 w-3 shrink-0" />
                      ) : (
                        <ArrowUpDown className="h-3 w-3 shrink-0 opacity-35" />
                      )}
                    </button>
                  </th>
                );
              })}
            </tr>
          </thead>
          <tbody>
            {pageRows.length === 0 ? (
              <tr>
                <td
                  colSpan={cols.length}
                  className="px-3 py-8 text-center text-sm text-ink-soft/70"
                >
                  Không có dòng khớp tìm kiếm.
                </td>
              </tr>
            ) : (
              pageRows.map((row, i) => (
                <tr
                  key={safePage * PAGE_SIZE + i}
                  className="border-b border-line/70 odd:bg-white even:bg-foam/50"
                >
                  {cols.map((c) => {
                    const v = row[c];
                    const cell =
                      typeof v === "number"
                        ? formatNumber(v, c)
                        : String(v ?? "—");
                    return (
                      <td key={c} className="px-3 py-2 text-ink-soft">
                        {cell}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <div className="flex items-center justify-between gap-2 border-t border-line bg-foam/70 px-3 py-1.5">
        <p className="text-[11px] text-ink-soft/65">
          Trang {safePage + 1}/{pageCount} · {PAGE_SIZE} dòng/trang
        </p>
        <div className="flex items-center gap-1">
          <button
            type="button"
            disabled={safePage <= 0}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-line bg-white text-ink-soft transition hover:border-teal/30 disabled:opacity-40"
            aria-label="Trang trước"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            disabled={safePage >= pageCount - 1}
            onClick={() => setPage((p) => Math.min(pageCount - 1, p + 1))}
            className="inline-flex h-7 w-7 items-center justify-center rounded-lg border border-line bg-white text-ink-soft transition hover:border-teal/30 disabled:opacity-40"
            aria-label="Trang sau"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
