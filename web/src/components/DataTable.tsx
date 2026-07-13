"use client";

import { formatNumber } from "@/lib/format";

export function DataTable({ data }: { data: Record<string, unknown>[] }) {
  if (!data.length) return null;
  const cols = Object.keys(data[0]);
  const rows = data.slice(0, 80);

  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className="max-h-[320px] overflow-auto scrollbar-thin">
        <table className="w-full min-w-[420px] border-collapse text-left text-[13px]">
          <thead className="sticky top-0 bg-mist/95 backdrop-blur">
            <tr>
              {cols.map((c) => (
                <th
                  key={c}
                  className="border-b border-line px-3 py-2.5 font-semibold text-ink-soft"
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr
                key={i}
                className="border-b border-line/70 odd:bg-white even:bg-foam/50"
              >
                {cols.map((c) => {
                  const v = row[c];
                  const cell =
                    typeof v === "number" ? formatNumber(v, c) : String(v ?? "—");
                  return (
                    <td key={c} className="px-3 py-2 text-ink-soft">
                      {cell}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {data.length > 80 && (
        <p className="border-t border-line bg-foam/70 px-3 py-1.5 text-[11px] text-ink-soft/65">
          Hiển thị 80 / {data.length} dòng
        </p>
      )}
    </div>
  );
}
